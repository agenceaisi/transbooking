import pytest
from rest_framework.test import APIClient

from apps.users.models import Role, User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_register_voyageur(api_client):
    response = api_client.post(
        "/api/v1/auth/register/",
        {
            "prenom": "Awa",
            "nom": "Ouedraogo",
            "phone": "+22670000001",
            "email": "awa@example.com",
            "password": "password123",
        },
        format="json",
    )

    assert response.status_code == 201
    user = User.objects.get(phone="+22670000001")
    assert user.role.name == Role.RoleName.VOYAGEUR
    assert user.check_password("password123")
    assert response.data["role"] == Role.RoleName.VOYAGEUR


@pytest.mark.django_db
def test_register_rejects_duplicate_phone(api_client):
    Role.objects.create(name=Role.RoleName.VOYAGEUR)
    User.objects.create_user(
        prenom="Awa",
        nom="Ouedraogo",
        phone="+22670000002",
        password="password123",
    )

    response = api_client.post(
        "/api/v1/auth/register/",
        {
            "prenom": "Awa",
            "nom": "Ouedraogo",
            "phone": "+22670000002",
            "password": "password123",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "phone" in response.data


@pytest.mark.django_db
def test_login_rejects_wrong_password(api_client):
    role = Role.objects.create(name=Role.RoleName.VOYAGEUR)
    User.objects.create_user(
        prenom="Awa",
        nom="Ouedraogo",
        phone="+22670000003",
        password="password123",
        role=role,
    )

    response = api_client.post(
        "/api/v1/auth/login/",
        {"phone": "+22670000003", "password": "bad-password"},
        format="json",
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_profile_update_allows_phone_and_email_only(api_client):
    role = Role.objects.create(name=Role.RoleName.VOYAGEUR)
    user = User.objects.create_user(
        prenom="Awa",
        nom="Ouedraogo",
        phone="+22670000004",
        password="password123",
        role=role,
    )
    api_client.force_authenticate(user=user)

    response = api_client.patch(
        "/api/v1/users/me/",
        {
            "phone": "+22670000005",
            "email": "new@example.com",
            "prenom": "Ignored",
        },
        format="json",
    )

    user.refresh_from_db()
    assert response.status_code == 200
    assert user.phone == "+22670000005"
    assert user.email == "new@example.com"
    assert user.prenom == "Awa"
