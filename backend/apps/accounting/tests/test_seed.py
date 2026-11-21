import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounting.models import AccountCatalog, FiscalPeriod
from apps.authentication.models import CompanyMembership, User
from apps.core.models import AuditLog
from apps.tenants.models import Company


pytestmark = pytest.mark.django_db

DEMO_PASSWORD = "Demo-Pass-2026!"


def counts():
    return {
        "companies": Company.objects.count(),
        "users": User.objects.count(),
        "memberships": CompanyMembership.objects.count(),
        "accounts": AccountCatalog.objects.count(),
        "periods": FiscalPeriod.objects.count(),
        "audit_logs": AuditLog.objects.count(),
    }


@pytest.fixture
def demo_password(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", DEMO_PASSWORD)
    return DEMO_PASSWORD


def test_seed_creates_v1_demo_data(demo_password):
    call_command("seed_accounting_data", force=True, verbosity=0)

    assert counts() == {
        "companies": 2,
        "users": 4,
        "memberships": 7,
        "accounts": 160,
        "periods": 4,
        "audit_logs": 2,
    }

    assert set(Company.objects.values_list("rfc", flat=True)) == {
        "CNO200101AB9",
        "SDA210515XY1",
    }

    socio = User.objects.get(email="socio@demo.mx")
    auxiliar = User.objects.get(email="auxiliar@demo.mx")
    auditor = User.objects.get(email="auditor@demo.mx")
    cliente = User.objects.get(email="cliente@demo.mx")
    for user in (socio, auxiliar, auditor, cliente):
        assert user.check_password(demo_password)

    assert socio.company_memberships.count() == 2
    assert auxiliar.company_memberships.count() == 2
    assert auditor.company_memberships.count() == 2
    assert cliente.company_memberships.count() == 1
    assert cliente.company_memberships.get().company.rfc == "CNO200101AB9"
    assert (
        cliente.company_memberships.get().role
        == CompanyMembership.Role.CLIENT
    )

    assert AccountCatalog.objects.values("company_id").distinct().count() == 2
    for company in Company.objects.all():
        assert AccountCatalog.objects.filter(company=company).count() == 80

    open_periods = FiscalPeriod.objects.filter(is_closed=False)
    closed_periods = FiscalPeriod.objects.filter(is_closed=True)
    assert open_periods.count() == 2
    assert closed_periods.count() == 2
    assert all(period.closed_by == socio for period in closed_periods)

    assert AuditLog.objects.filter(
        action=AuditLog.ActionType.PERIOD_CLOSED
    ).count() == 2


def test_seed_is_idempotent(demo_password):
    call_command("seed_accounting_data", force=True, verbosity=0)
    first_counts = counts()
    first_company_ids = set(Company.objects.values_list("pk", flat=True))
    first_account_ids = set(AccountCatalog.objects.values_list("pk", flat=True))

    call_command("seed_accounting_data", force=True, verbosity=0)

    assert counts() == first_counts
    assert set(Company.objects.values_list("pk", flat=True)) == first_company_ids
    assert set(AccountCatalog.objects.values_list("pk", flat=True)) == first_account_ids


def test_seed_refuses_debug_false_without_force(demo_password, monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)

    with pytest.raises(CommandError, match="DEBUG=False"):
        call_command("seed_accounting_data", verbosity=0)

    assert Company.objects.count() == 0


def test_seed_requires_demo_password(monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)

    with pytest.raises(CommandError, match="DEMO_PASSWORD"):
        call_command("seed_accounting_data", force=True, verbosity=0)

    assert Company.objects.count() == 0
