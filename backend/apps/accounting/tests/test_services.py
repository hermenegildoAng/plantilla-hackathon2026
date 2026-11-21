from datetime import date

import pytest
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.accounting.models import AccountCatalog, FiscalPeriod
from apps.accounting.services import (
    clone_master_sat_catalog,
    close_period,
    get_or_create_period,
    reopen_period,
)
from apps.core.models import AuditLog


pytestmark = pytest.mark.django_db


def test_clone_master_catalog_creates_hierarchical_sat_accounts(make_company):
    company = make_company()

    created = clone_master_sat_catalog(company)

    assert len(created) == 80
    assert AccountCatalog.objects.filter(company=company).count() == 80

    banks_group = AccountCatalog.objects.get(company=company, code="102.01")
    assert banks_group.name == "Bancos nacionales"
    assert banks_group.sat_group_code == "102.01"
    assert banks_group.parent.code == "102"
    assert banks_group.is_selectable is False

    bbva = AccountCatalog.objects.get(company=company, code="102.01.001")
    assert bbva.parent == banks_group
    assert bbva.sat_group_code == "102.01"
    assert bbva.is_selectable is True

    assert AccountCatalog.objects.filter(
        company=company,
        sat_group_code="118.01",
        name__icontains="IVA acreditable",
    ).exists()
    assert AccountCatalog.objects.filter(
        company=company,
        sat_group_code="207.01",
        name__icontains="IVA trasladado",
    ).exists()
    assert AccountCatalog.objects.filter(
        company=company,
        sat_group_code__in=["216.04", "216.10"],
    ).count() == 2
    assert AccountCatalog.objects.filter(
        company=company,
        sat_group_code="601.34",
        name__icontains="Honorarios",
    ).exists()

    roots = set(
        AccountCatalog.objects.filter(
            company=company,
            parent__isnull=True,
        ).values_list("code", flat=True)
    )
    assert roots == {"100", "200", "300", "400", "500", "600", "800"}


def test_clone_master_catalog_is_isolated_per_company(make_company):
    company_a = make_company()
    company_b = make_company()

    clone_master_sat_catalog(company_a)
    clone_master_sat_catalog(company_b)

    assert AccountCatalog.objects.filter(company=company_a).count() == 80
    assert AccountCatalog.objects.filter(company=company_b).count() == 80
    assert AccountCatalog.objects.filter(company=company_a, code="102.01").exists()
    assert AccountCatalog.objects.filter(company=company_b, code="102.01").exists()
    assert not AccountCatalog.objects.filter(company=company_a).filter(
        pk__in=AccountCatalog.objects.filter(company=company_b).values("pk")
    ).exists()


def test_clone_master_catalog_is_idempotent(make_company):
    company = make_company()

    clone_master_sat_catalog(company)
    created_again = clone_master_sat_catalog(company)

    assert created_again == []
    assert AccountCatalog.objects.filter(company=company).count() == 80


def test_account_code_is_unique_per_company_only(make_company):
    company_a = make_company()
    company_b = make_company()
    AccountCatalog.objects.create(
        company=company_a,
        code="999.01",
        sat_group_code="999.01",
        name="Cuenta auxiliar",
        account_type=AccountCatalog.AccountType.ASSET,
        nature=AccountCatalog.Nature.DEBIT,
    )
    AccountCatalog.objects.create(
        company=company_b,
        code="999.01",
        sat_group_code="999.01",
        name="Cuenta auxiliar",
        account_type=AccountCatalog.AccountType.ASSET,
        nature=AccountCatalog.Nature.DEBIT,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AccountCatalog.objects.create(
                company=company_a,
                code="999.01",
                sat_group_code="999.01",
                name="Duplicada",
                account_type=AccountCatalog.AccountType.ASSET,
                nature=AccountCatalog.Nature.DEBIT,
            )


def test_get_or_create_period_resolves_by_company_and_month(make_company):
    company = make_company()

    january = get_or_create_period(company, date(2026, 1, 15))
    same_january = get_or_create_period(company, date(2026, 1, 31))

    assert january.pk == same_january.pk
    assert (january.year, january.month) == (2026, 1)
    assert FiscalPeriod.objects.filter(company=company).count() == 1

    february = get_or_create_period(company, date(2026, 2, 1))
    assert february.pk != january.pk
    assert FiscalPeriod.objects.filter(company=company).count() == 2


def test_close_period_sets_fields_and_creates_audit_log(
    make_user, make_company
):
    user = make_user()
    company = make_company()
    period = get_or_create_period(company, date(2026, 3, 10))

    closed = close_period(period, user=user, ip_address="203.0.113.10")

    assert closed.is_closed is True
    assert closed.closed_at is not None
    assert closed.closed_by == user

    log = AuditLog.objects.get(
        company=company,
        action=AuditLog.ActionType.PERIOD_CLOSED,
    )
    assert log.user == user
    assert log.target_model == "FiscalPeriod"
    assert log.target_id == str(period.pk)
    assert log.ip_address == "203.0.113.10"
    assert log.previous_state["is_closed"] is False
    assert log.new_state["is_closed"] is True

    with pytest.raises(ValidationError):
        close_period(closed, user=user)


def test_reopen_period_requires_justification_and_creates_audit_log(
    make_user, make_company
):
    user = make_user()
    company = make_company()
    period = get_or_create_period(company, date(2026, 3, 10))
    close_period(period, user=user, ip_address="203.0.113.10")

    with pytest.raises(ValidationError):
        reopen_period(period, user=user, justification="corto")

    assert not AuditLog.objects.filter(
        action=AuditLog.ActionType.PERIOD_REOPENED
    ).exists()

    reopened = reopen_period(
        period,
        user=user,
        justification="Reclasificación de factura complementaria de pago.",
        ip_address="203.0.113.20",
    )

    assert reopened.is_closed is False
    assert reopened.closed_at is None
    assert reopened.closed_by is None

    log = AuditLog.objects.get(
        company=company,
        action=AuditLog.ActionType.PERIOD_REOPENED,
    )
    assert log.justification.startswith("Reclasificación")
    assert log.ip_address == "203.0.113.20"
    assert log.previous_state["is_closed"] is True
    assert log.new_state["is_closed"] is False
