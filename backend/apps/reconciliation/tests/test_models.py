import hashlib

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.reconciliation.models import BankMovement
from apps.reconciliation.tests.helpers import make_movement


pytestmark = pytest.mark.django_db


def test_amount_property_uses_deposit_or_withdrawal(tenant_user):
    _user, company, _membership, _client = tenant_user()
    deposit = make_movement(company, amount="1500.00", kind="deposit")
    withdrawal = make_movement(company, amount="250.00", kind="withdrawal")

    assert deposit.amount == 1500
    assert withdrawal.amount == -250


def test_movement_rejects_deposit_and_withdrawal_together(tenant_user):
    _user, company, _membership, _client = tenant_user()
    movement = BankMovement(
        company=company,
        date="2026-05-10",
        reference="REF",
        description="Ambos",
        deposit=100,
        withdrawal=50,
        row_hash="a" * 64,
    )

    with pytest.raises(ValidationError):
        movement.full_clean()


def test_movement_rejects_zero_amounts(tenant_user):
    _user, company, _membership, _client = tenant_user()
    movement = BankMovement(
        company=company,
        date="2026-05-10",
        reference="REF",
        description="Cero",
        deposit=0,
        withdrawal=0,
        row_hash="b" * 64,
    )

    with pytest.raises(ValidationError):
        movement.full_clean()


def test_row_hash_is_unique_per_company(tenant_user, make_company):
    _user, company, _membership, _client = tenant_user()
    other_company = make_company()
    row_hash = hashlib.sha256(b"same-row").hexdigest()

    BankMovement.objects.create(
        company=company,
        date="2026-05-10",
        reference="REF",
        description="Uno",
        deposit=100,
        withdrawal=0,
        row_hash=row_hash,
    )
    # The same row is allowed in a different company.
    BankMovement.objects.create(
        company=other_company,
        date="2026-05-10",
        reference="REF",
        description="Uno",
        deposit=100,
        withdrawal=0,
        row_hash=row_hash,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BankMovement.objects.create(
                company=company,
                date="2026-05-10",
                reference="REF",
                description="Uno",
                deposit=100,
                withdrawal=0,
                row_hash=row_hash,
            )
