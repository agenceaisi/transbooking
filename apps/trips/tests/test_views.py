from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.geography.tests.factories import StationFactory
from apps.routes.tests.factories import RouteFactory, RouteStopFactory
from apps.trips.models import Trip
from apps.users.models import AgentProfile, Role, User
from apps.vehicles.tests.factories import VehicleFactory

from .factories import TripFactory


@pytest.fixture
def api_client():
    return APIClient()


def _make_user(role_name: str, phone: str) -> User:
    role, _ = Role.objects.get_or_create(name=role_name)
    return User.objects.create_user(
        prenom="Test", nom="User", phone=phone, password="password123", role=role
    )


def _company_admin(api_client, company, phone):
    admin = _make_user(Role.RoleName.COMPANY_ADMIN, phone)
    company.admin_user = admin
    company.save(update_fields=["admin_user"])
    api_client.force_authenticate(user=admin)
    return admin


# --------------------------------------------------------------------------- #
# Company admin
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_create_trip_initialises_available_seats(api_client):
    route = RouteFactory()
    vehicle = VehicleFactory(company=route.company, total_seats=50)
    _company_admin(api_client, route.company, "+22670000400")

    response = api_client.post(
        "/api/v1/company/trips/",
        {
            "route": route.id,
            "vehicle": vehicle.id,
            "departure_time": (timezone.now() + timedelta(days=2)).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 201
    trip = Trip.objects.get(pk=response.data["id"])
    assert trip.available_seats == 50
    assert trip.price == route.base_price


@pytest.mark.django_db
def test_company_admin_only_sees_own_trips(api_client):
    own = TripFactory()
    TripFactory()  # autre compagnie
    _company_admin(api_client, own.route.company, "+22670000401")

    response = api_client.get("/api/v1/company/trips/")

    assert response.status_code == 200
    ids = [t["id"] for t in response.data["results"]]
    assert ids == [own.id]


@pytest.mark.django_db
def test_delete_trip_cancels_and_notifies(api_client, monkeypatch):
    trip = TripFactory()
    _company_admin(api_client, trip.route.company, "+22670000402")
    monkeypatch.setattr("apps.trips.services._passenger_phones", lambda t: [])

    response = api_client.delete(
        f"/api/v1/company/trips/{trip.id}/", {"reason": "Greve"}, format="json"
    )

    assert response.status_code == 200
    trip.refresh_from_db()
    assert trip.status == Trip.TripStatus.CANCELLED


# --------------------------------------------------------------------------- #
# Recherche publique
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_public_search_filters_by_cities_and_passengers(api_client):
    route = RouteFactory()
    match = TripFactory(route=route, available_seats=10)
    # Pas assez de places.
    TripFactory(route=route, available_seats=1)
    # Autre trajet.
    TripFactory()

    response = api_client.get(
        "/api/v1/trips/search/",
        {
            "origin_city": route.origin_city_id,
            "dest_city": route.destination_city_id,
            "passengers": 5,
        },
    )

    assert response.status_code == 200
    ids = [t["id"] for t in response.data["results"]]
    assert ids == [match.id]


@pytest.mark.django_db
def test_public_search_direct_excludes_routes_with_stops(api_client):
    route_with_stop = RouteFactory()
    RouteStopFactory(route=route_with_stop, stop_order=1)
    TripFactory(route=route_with_stop)
    direct_trip = TripFactory()

    response = api_client.get("/api/v1/trips/search/", {"direct": "true"})

    assert response.status_code == 200
    ids = [t["id"] for t in response.data["results"]]
    assert direct_trip.id in ids
    assert all(tid != route_with_stop.trips.first().id for tid in ids)


@pytest.mark.django_db
def test_public_trip_detail_exposes_available_seats(api_client):
    trip = TripFactory()

    response = api_client.get(f"/api/v1/trips/{trip.id}/")

    assert response.status_code == 200
    assert "available_seat_numbers" in response.data


# --------------------------------------------------------------------------- #
# Agent — programme du jour
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_agent_today_trips_filtered_by_station(api_client):
    route = RouteFactory()
    station = StationFactory(company=route.company, city=route.origin_city)
    route.origin_station = station
    route.save(update_fields=["origin_station"])

    today_trip = TripFactory(route=route, departure_time=timezone.now())
    # Voyage de demain : exclu.
    TripFactory(route=route, departure_time=timezone.now() + timedelta(days=1))

    agent = _make_user(Role.RoleName.AGENT_GUICHET, "+22670000403")
    AgentProfile.objects.create(
        user=agent,
        company=route.company,
        agent_type=AgentProfile.AgentType.GUICHET,
        station=station,
    )
    api_client.force_authenticate(user=agent)

    response = api_client.get("/api/v1/agent/trips/today/")

    assert response.status_code == 200
    ids = [t["id"] for t in response.data]
    assert ids == [today_trip.id]
