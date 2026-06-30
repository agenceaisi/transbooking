import pytest
from django.core.exceptions import ValidationError

from apps.companies.models import CompanyStatus
from apps.companies.services import (
    activate_company,
    approve_company,
    reject_company,
    suspend_company,
)

from .factories import CompanyFactory


@pytest.mark.django_db
def test_approve_company_sets_active():
    company = CompanyFactory(status=CompanyStatus.PENDING)
    approve_company(company)
    company.refresh_from_db()
    assert company.status == CompanyStatus.ACTIVE


@pytest.mark.django_db
def test_approve_company_rejects_non_pending():
    company = CompanyFactory(status=CompanyStatus.ACTIVE)
    with pytest.raises(ValidationError):
        approve_company(company)


@pytest.mark.django_db
def test_reject_company_requires_reason():
    company = CompanyFactory(status=CompanyStatus.PENDING)
    with pytest.raises(ValidationError):
        reject_company(company, "")


@pytest.mark.django_db
def test_reject_company_stores_reason():
    company = CompanyFactory(status=CompanyStatus.PENDING)
    reject_company(company, "Documents manquants")
    company.refresh_from_db()
    assert company.status == CompanyStatus.REJECTED
    assert company.rejection_reason == "Documents manquants"


@pytest.mark.django_db
def test_suspend_then_activate():
    company = CompanyFactory(status=CompanyStatus.ACTIVE)
    suspend_company(company, "Impayes")
    company.refresh_from_db()
    assert company.status == CompanyStatus.SUSPENDED
    assert company.suspension_reason == "Impayes"

    activate_company(company)
    company.refresh_from_db()
    assert company.status == CompanyStatus.ACTIVE
    assert company.suspension_reason == ""


@pytest.mark.django_db
def test_suspend_requires_reason():
    company = CompanyFactory(status=CompanyStatus.ACTIVE)
    with pytest.raises(ValidationError):
        suspend_company(company, "  ")
