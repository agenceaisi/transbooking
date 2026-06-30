from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.routes.tests.factories import RouteFactory
from apps.trips.models import Trip
from apps.trips.services import cancel_trip, generate_trips
from apps.vehicles.models import Vehicle
from apps.vehicles.tests.factories import VehicleFactory

from .factories import TripFactory


@pytest.mark.django_db
def test_generate_trips_creates_expected_count():
    route = RouteFactory()
    vehicle = VehicleFactory(company=route.company, total_seats=40)
    # Tous les jours de la semaine -> 7 voyages sur 7 jours.
    config = [{"time": "06:00", "days": [0, 1, 2, 3, 4, 5, 6], "vehicle_id": vehicle.id}]

    trips = generate_trips(route.id, config, days=7)

    assert len(trips) == 7
    assert all(t.available_seats == 40 for t in trips)
    assert all(t.price == route.base_price for t in trips)


@pytest.mark.django_db
def test_generate_trips_respects_weekday_filter():
    route = RouteFactory()
    vehicle = VehicleFactory(company=route.company)
    # Un seul jour de la semaine actif -> au plus 1 voyage sur 7 jours.
    config = [{"time": "08:00", "days": [0], "vehicle_id": vehicle.id}]

    trips = generate_trips(route.id, config, days=7)

    assert len(trips) == 1
    assert trips[0].departure_time.weekday() == 0


@pytest.mark.django_db
def test_generate_trips_rejects_vehicle_in_maintenance():
    route = RouteFactory()
    vehicle = VehicleFactory(
        company=route.company, status=Vehicle.VehicleStatus.MAINTENANCE
    )
    config = [{"time": "06:00", "days": [0, 1, 2, 3, 4, 5, 6], "vehicle_id": vehicle.id}]

    with pytest.raises(ValidationError):
        generate_trips(route.id, config, days=7)


@pytest.mark.django_db
def test_cancel_trip_sets_status_and_sends_sms(monkeypatch):
    trip = TripFactory()
    sent = []
    monkeypatch.setattr(
        "apps.trips.services._passenger_phones", lambda t: ["+22670000999"]
    )
    monkeypatch.setattr(
        "apps.trips.services.send_sms", lambda phone, message: sent.append(phone)
    )

    cancel_trip(trip, "Panne mecanique")

    trip.refresh_from_db()
    assert trip.status == Trip.TripStatus.CANCELLED
    assert trip.cancellation_reason == "Panne mecanique"
    assert sent == ["+22670000999"]


@pytest.mark.django_db
def test_cancel_trip_already_cancelled_raises():
    trip = TripFactory(status=Trip.TripStatus.CANCELLED)

    with pytest.raises(ValidationError):
        cancel_trip(trip, "Deja annule")
