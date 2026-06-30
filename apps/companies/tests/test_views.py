import pytest
from rest_framework.test import APIClient

from apps.companies.models import Company, CompanyStatus
from apps.users.models import Role, User

from .factories import CompanyFactory


@pytest.fixture
def api_client():
    return APIClient()


def _make_user(role_name: str, phone: str) -> User:
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(
        prenom="Test",
        nom="User",
        phone=phone,
        password="password123",
        role=role,
    )


@pytest.mark.django_db
def test_public_companies_lists_only_active(api_client):
    CompanyFactory(status=CompanyStatus.ACTIVE, name="Active Co")
    CompanyFactory(status=CompanyStatus.PENDING, name="Pending Co")

    response = api_client.get("/api/v1/public/companies/")

    assert response.status_code == 200
    names = [c["name"] for c in response.data["results"]]
    assert "Active Co" in names
    assert "Pending Co" not in names


@pytest.mark.django_db
def test_super_admin_can_suspend_company(api_client):
    company = CompanyFactory(status=CompanyStatus.ACTIVE)
    admin = _make_user(Role.RoleName.SUPER_ADMIN, "+22670000010")
    api_client.force_authenticate(user=admin)

    response = api_client.post(
        f"/api/v1/super/companies/{company.id}/suspend/",
        {"reason": "Impayes"},
        format="json",
    )

    assert response.status_code == 200
    company.refresh_from_db()
    assert company.status == CompanyStatus.SUSPENDED


@pytest.mark.django_db
def test_company_requests_lists_pending_and_approves(api_client):
    company = CompanyFactory(status=CompanyStatus.PENDING)
    admin = _make_user(Role.RoleName.SUPER_ADMIN, "+22670000011")
    api_client.force_authenticate(user=admin)

    list_response = api_client.get("/api/v1/super/company-requests/")
    assert list_response.status_code == 200
    assert any(c["id"] == company.id for c in list_response.data["results"])

    approve_response = api_client.post(
        f"/api/v1/super/company-requests/{company.id}/approve/"
    )
    assert approve_response.status_code == 200
    company.refresh_from_db()
    assert company.status == CompanyStatus.ACTIVE


@pytest.mark.django_db
def test_company_admin_cannot_access_other_company_settings(api_client):
    company_a = CompanyFactory(name="Company A")
    company_b = CompanyFactory(name="Company B")

    admin_a = _make_user(Role.RoleName.COMPANY_ADMIN, "+22670000020")
    company_a.admin_user = admin_a
    company_a.save(update_fields=["admin_user"])

    admin_b = _make_user(Role.RoleName.COMPANY_ADMIN, "+22670000021")
    company_b.admin_user = admin_b
    company_b.save(update_fields=["admin_user"])

    api_client.force_authenticate(user=admin_a)
    response = api_client.get("/api/v1/company/settings/")

    assert response.status_code == 200
    # L'admin A ne voit QUE sa propre compagnie, jamais celle de B.
    assert response.data["name"] == "Company A"
    assert response.data["name"] != "Company B"


@pytest.mark.django_db
def test_company_admin_without_company_gets_404(api_client):
    admin = _make_user(Role.RoleName.COMPANY_ADMIN, "+22670000022")
    api_client.force_authenticate(user=admin)

    response = api_client.get("/api/v1/company/settings/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_voyageur_cannot_access_super_companies(api_client):
    CompanyFactory()
    voyageur = _make_user(Role.RoleName.VOYAGEUR, "+22670000030")
    api_client.force_authenticate(user=voyageur)

    response = api_client.get("/api/v1/super/companies/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_company_admin_updates_payment_methods(api_client):
    company = CompanyFactory()
    admin = _make_user(Role.RoleName.COMPANY_ADMIN, "+22670000040")
    company.admin_user = admin
    company.save(update_fields=["admin_user"])
    api_client.force_authenticate(user=admin)

    response = api_client.patch(
        "/api/v1/company/settings/payment-methods/",
        {"payment_methods": [{"method": "orange_money", "is_active": True}]},
        format="json",
    )

    assert response.status_code == 200
    assert company.payment_methods.filter(method="orange_money", is_active=True).exists()
