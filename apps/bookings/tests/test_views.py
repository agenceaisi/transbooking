from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import BoardingValidation, Booking, BookingStatus
from apps.routes.tests.factories import RouteFactory
from apps.trips.tests.factories import TripFactory
from apps.users.models import AgentProfile, Role, User
from apps.vehicles.tests.factories import VehicleFactory

from .factories import BookingFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def _mute_sms(monkeypatch):
    monkeypatch.setattr("apps.bookings.services.send_sms", lambda *a, **k: None)


def _make_user(role_name: str, phone: str) -> User:
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(
        prenom="Test", nom="User", phone=phone, password="password123", role=role
    )


def _trip_for_company(company, **kwargs):
    route = RouteFactory(company=company)
    vehicle = VehicleFactory(company=company, total_seats=kwargs.pop("total_seats", 30))
    return TripFactory(route=route, vehicle=vehicle, **kwargs)


# --------------------------------------------------------------------------- #
# Voyageur
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_voyageur_creates_booking(api_client):
    trip = TripFactory(available_seats=30)
    voyageur = _make_user(Role.RoleName.VOYAGEUR, "+22670001000")
    api_client.force_authenticate(user=voyageur)

    response = api_client.post(
        "/api/v1/bookings/", {"trip": trip.id}, format="json"
    )

    assert response.status_code == 201
    assert response.data["status"] == BookingStatus.PENDING
    assert response.data["ticket_number"].startswith("BF")
    booking = Booking.objects.get(ticket_number=response.data["ticket_number"])
    assert booking.user == voyageur


@pytest.mark.django_db
def test_voyageur_only_sees_own_bookings(api_client):
    mine = BookingFactory()
    BookingFactory()  # autre voyageur
    api_client.force_authenticate(user=mine.user)
    # mine.user n'a pas de role voyageur (UserFactory en met un par defaut).
    role, _ = Role.objects.get_or_create(name=Role.RoleName.VOYAGEUR)
    mine.user.role = role
    mine.user.save(update_fields=["role"])

    response = api_client.get("/api/v1/bookings/")

    assert response.status_code == 200
    ids = [b["id"] for b in response.data["results"]]
    assert ids == [mine.id]


@pytest.mark.django_db
def test_voyageur_cancels_booking_restores_seat(api_client):
    trip = TripFactory(
        available_seats=29, departure_time=timezone.now() + timedelta(days=2)
    )
    voyageur = _make_user(Role.RoleName.VOYAGEUR, "+22670001001")
    booking = BookingFactory(trip=trip, user=voyageur, status=BookingStatus.PAID)
    api_client.force_authenticate(user=voyageur)

    response = api_client.post(f"/api/v1/bookings/{booking.id}/cancel/")

    assert response.status_code == 200
    booking.refresh_from_db()
    trip.refresh_from_db()
    assert booking.status == BookingStatus.CANCELLED
    assert trip.available_seats == 30


@pytest.mark.django_db
def test_voyageur_cancel_too_late_returns_409(api_client):
    trip = TripFactory(departure_time=timezone.now() + timedelta(minutes=30))
    voyageur = _make_user(Role.RoleName.VOYAGEUR, "+22670001002")
    booking = BookingFactory(trip=trip, user=voyageur)
    api_client.force_authenticate(user=voyageur)

    response = api_client.post(f"/api/v1/bookings/{booking.id}/cancel/")

    assert response.status_code == 409


@pytest.mark.django_db
def test_voyageur_downloads_ticket_pdf(api_client):
    voyageur = _make_user(Role.RoleName.VOYAGEUR, "+22670001003")
    booking = BookingFactory(user=voyageur)
    api_client.force_authenticate(user=voyageur)

    response = api_client.get(f"/api/v1/bookings/{booking.id}/ticket/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


# --------------------------------------------------------------------------- #
# Agent guichet
# --------------------------------------------------------------------------- #
def _agent(api_client, company, phone, agent_type):
    agent = _make_user(
        Role.RoleName.AGENT_GUICHET
        if agent_type == AgentProfile.AgentType.GUICHET
        else Role.RoleName.CONTROLEUR,
        phone,
    )
    AgentProfile.objects.create(
        user=agent, company=company, agent_type=agent_type
    )
    api_client.force_authenticate(user=agent)
    return agent


@pytest.mark.django_db
def test_agent_creates_offline_booking(api_client):
    trip = TripFactory(available_seats=30)
    _agent(
        api_client,
        trip.route.company,
        "+22670002000",
        AgentProfile.AgentType.GUICHET,
    )

    response = api_client.post(
        "/api/v1/agent/bookings/",
        {
            "trip": trip.id,
            "first_name": "Aminata",
            "last_name": "TRAORE",
            "phone": "+22670000123",
            "payment_method": "cash",
            "is_offline": True,
            "offline_created_at": timezone.now().isoformat(),
        },
        format="json",
    )

    assert response.status_code == 201
    booking = Booking.objects.get(ticket_number=response.data["ticket_number"])
    assert booking.is_offline is True
    assert booking.synced_at is None
    assert booking.status == BookingStatus.PAID
    assert booking.agent is not None


@pytest.mark.django_db
def test_agent_mobile_money_requires_transaction_ref(api_client):
    trip = TripFactory(available_seats=30)
    _agent(
        api_client,
        trip.route.company,
        "+22670002001",
        AgentProfile.AgentType.GUICHET,
    )

    response = api_client.post(
        "/api/v1/agent/bookings/",
        {
            "trip": trip.id,
            "first_name": "Aminata",
            "last_name": "TRAORE",
            "phone": "+22670000123",
            "payment_method": "orange_money",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "transaction_ref" in response.data


@pytest.mark.django_db
def test_agent_looks_up_booking_by_ticket_number(api_client):
    booking = BookingFactory()
    _agent(
        api_client,
        booking.trip.route.company,
        "+22670002002",
        AgentProfile.AgentType.GUICHET,
    )

    response = api_client.get(f"/api/v1/agent/bookings/{booking.ticket_number}/")

    assert response.status_code == 200
    assert response.data["ticket_number"] == booking.ticket_number


# --------------------------------------------------------------------------- #
# Controleur — scan & embarquement
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_controleur_scan_invalid_ticket_returns_404(api_client):
    company = VehicleFactory().company
    _agent(api_client, company, "+22670003000", AgentProfile.AgentType.CONTROLEUR)

    response = api_client.post(
        "/api/v1/agent/scan/", {"qr_data": "BF2026000000"}, format="json"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_controleur_scan_valid_ticket_returns_green(api_client):
    booking = BookingFactory(status=BookingStatus.PAID)
    _agent(
        api_client,
        booking.trip.route.company,
        "+22670003001",
        AgentProfile.AgentType.CONTROLEUR,
    )

    response = api_client.post(
        "/api/v1/agent/scan/", {"qr_data": booking.ticket_number}, format="json"
    )

    assert response.status_code == 200
    assert response.data["color"] == "green"


@pytest.mark.django_db
def test_controleur_manual_check_in(api_client):
    booking = BookingFactory(status=BookingStatus.PAID)
    _agent(
        api_client,
        booking.trip.route.company,
        "+22670003002",
        AgentProfile.AgentType.CONTROLEUR,
    )

    response = api_client.post(
        f"/api/v1/agent/trips/{booking.trip_id}/boarding/{booking.id}/"
    )

    assert response.status_code == 201
    assert BoardingValidation.objects.filter(booking=booking).exists()


@pytest.mark.django_db
def test_controleur_bulk_check_in_requires_confirm(api_client):
    trip = TripFactory()
    BookingFactory(trip=trip, status=BookingStatus.PAID, seat_number="1")
    _agent(
        api_client,
        trip.route.company,
        "+22670003003",
        AgentProfile.AgentType.CONTROLEUR,
    )

    no_confirm = api_client.post(f"/api/v1/agent/trips/{trip.id}/boarding/all/")
    assert no_confirm.status_code == 400

    confirmed = api_client.post(
        f"/api/v1/agent/trips/{trip.id}/boarding/all/",
        {"confirm": True},
        format="json",
    )
    assert confirmed.status_code == 200
    assert confirmed.data["boarded"] == 1


# --------------------------------------------------------------------------- #
# Admin compagnie
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_company_admin_only_sees_own_bookings(api_client):
    own_trip = _trip_for_company(VehicleFactory().company)
    mine = BookingFactory(trip=own_trip)
    BookingFactory()  # autre compagnie

    admin = _make_user(Role.RoleName.COMPANY_ADMIN, "+22670004000")
    company = own_trip.route.company
    company.admin_user = admin
    company.save(update_fields=["admin_user"])
    api_client.force_authenticate(user=admin)

    response = api_client.get("/api/v1/company/bookings/")

    assert response.status_code == 200
    ids = [b["id"] for b in response.data["results"]]
    assert ids == [mine.id]


@pytest.mark.django_db
def test_company_admin_exports_bookings_pdf(api_client):
    own_trip = _trip_for_company(VehicleFactory().company)
    BookingFactory(trip=own_trip)
    admin = _make_user(Role.RoleName.COMPANY_ADMIN, "+22670004001")
    company = own_trip.route.company
    company.admin_user = admin
    company.save(update_fields=["admin_user"])
    api_client.force_authenticate(user=admin)

    response = api_client.get("/api/v1/company/bookings/export/?format=pdf")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


@pytest.mark.django_db
def test_voyageur_cannot_access_agent_endpoint(api_client):
    trip = TripFactory()
    voyageur = _make_user(Role.RoleName.VOYAGEUR, "+22670005000")
    api_client.force_authenticate(user=voyageur)

    response = api_client.post(
        "/api/v1/agent/bookings/",
        {
            "trip": trip.id,
            "first_name": "X",
            "last_name": "Y",
            "phone": "+22670000111",
            "payment_method": "cash",
        },
        format="json",
    )

    assert response.status_code == 403
