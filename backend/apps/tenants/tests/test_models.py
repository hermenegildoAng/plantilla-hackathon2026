import pytest
from django.core.exceptions import ValidationError

from apps.tenants.models import Company


pytestmark = pytest.mark.django_db


def build_company(**overrides):
    data = {
        "rfc": "CNO200101AB9",
        "legal_name": "Comercializadora del Norte",
        "tax_regime": Company.TaxRegime.GENERAL_PM,
    }
    data.update(overrides)
    return Company(**data)


@pytest.mark.parametrize(
    "rfc",
    [
        "CME210514AB9",
        "GARC850912H10",
        "CNO200101AB9",
        "SDA210515XY1",
    ],
)
def test_valid_rfcs_pass_validation(rfc):
    company = build_company(rfc=rfc, legal_name=f"Empresa {rfc}")

    company.full_clean()
    company.save()

    assert company.rfc == rfc


def test_invalid_rfc_is_rejected():
    company = build_company(rfc="CNO200101ABC")

    with pytest.raises(ValidationError) as exc_info:
        company.full_clean()

    assert "rfc" in exc_info.value.message_dict
    assert "Formato de RFC inválido según reglas del SAT." in str(exc_info.value)


def test_rfc_is_normalized_to_uppercase_on_save():
    company = build_company(rfc="cno200101ab9", legal_name="Empresa minúsculas")

    company.save()
    company.refresh_from_db()

    assert company.rfc == "CNO200101AB9"


def test_fiscal_year_start_defaults_to_january():
    company = build_company()

    assert company.fiscal_year_start == 1


def test_fiscal_year_start_rejects_out_of_range_values():
    company = build_company(fiscal_year_start=13)

    with pytest.raises(ValidationError) as exc_info:
        company.full_clean()

    assert "fiscal_year_start" in exc_info.value.message_dict
