import pytest
from django.db import IntegrityError

from apps.authentication.models import CompanyMembership, Profile, User


@pytest.mark.django_db
def test_create_user_normalizes_email_and_hashes_password():
    user = User.objects.create_user("Test.User@Example.COM", "s3cret-pass")

    assert user.email == "test.user@example.com"
    assert user.check_password("s3cret-pass")
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.is_active is True


@pytest.mark.django_db
def test_create_superuser_sets_required_flags():
    user = User.objects.create_superuser("admin@example.com", "s3cret-pass")

    assert user.is_staff is True
    assert user.is_superuser is True


@pytest.mark.django_db
def test_email_is_unique():
    User.objects.create_user("duplicate@example.com", "s3cret-pass")

    with pytest.raises(IntegrityError):
        User.objects.create_user("duplicate@example.com", "other-pass")


def test_email_is_the_username_field():
    assert User.USERNAME_FIELD == "email"
    assert User.REQUIRED_FIELDS == []


@pytest.mark.django_db
def test_create_user_requires_email():
    with pytest.raises(ValueError, match="correo electrónico"):
        User.objects.create_user("", "s3cret-pass")


@pytest.mark.django_db
def test_full_name_falls_back_to_email():
    user = User.objects.create_user("sin-nombre@example.com", "s3cret-pass")
    assert user.full_name == "sin-nombre@example.com"

    user.first_name = "Laura"
    user.last_name = "Méndez"
    user.save()
    assert user.full_name == "Laura Méndez"


@pytest.mark.django_db
def test_profile_defaults_and_default_company(make_company):
    user = User.objects.create_user("perfil@example.com", "s3cret-pass")
    company = make_company()

    profile = Profile.objects.create(user=user, default_company=company)

    assert profile.phone == ""
    assert profile.professional_license == ""
    assert user.profile == profile
    assert company.default_for_profiles.get() == profile


@pytest.mark.django_db
def test_membership_defaults_to_accountant_and_role_per_company(
    make_user, make_company
):
    user = make_user()
    company = make_company()

    membership = CompanyMembership.objects.create(user=user, company=company)

    assert membership.role == CompanyMembership.Role.ACCOUNTANT
    assert membership.is_active is True


@pytest.mark.django_db
def test_membership_is_unique_per_user_and_company(make_user, make_company):
    user = make_user()
    company = make_company()
    CompanyMembership.objects.create(user=user, company=company)

    with pytest.raises(IntegrityError):
        CompanyMembership.objects.create(user=user, company=company)


@pytest.mark.django_db
def test_membership_allows_same_user_in_different_companies(
    make_user, make_company, make_membership
):
    user = make_user()
    company_a = make_company()
    company_b = make_company()

    make_membership(user, company_a, CompanyMembership.Role.PARTNER)
    make_membership(user, company_b, CompanyMembership.Role.AUDITOR)

    assert user.company_memberships.count() == 2
