from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.routes.models import Route
from apps.vehicles.models import Vehicle
from apps.vehicles.services import ensure_vehicle_assignable
from utils.sms import send_sms

from .models import Trip


def _parse_time(value: str) -> time:
    """Parse an ``HH:MM`` string into a ``time`` object.

    Args:
        value: Time string such as ``"06:00"``.

    Returns:
        The parsed ``time``.

    Raises:
        ValidationError: If the format is invalid.
    """
    try:
        hour, minute = (int(part) for part in value.split(":"))
        return time(hour=hour, minute=minute)
    except (ValueError, AttributeError):
        raise ValidationError(f"Heure invalide : {value!r} (format attendu HH:MM).")


@transaction.atomic
def generate_trips(route_id: int, schedule_config: list[dict], days: int) -> list[Trip]:
    """Generate trips for a route over a rolling window of days.

    Args:
        route_id: Primary key of the route to schedule.
        schedule_config: List of slots, each as
            ``{"time": "06:00", "days": [0, 1, 2, 3, 4, 5, 6], "vehicle_id": 3}``
            where ``days`` are weekday indexes (Monday=0).
        days: Number of days from today (inclusive) to generate.

    Returns:
        The list of created trips.

    Raises:
        ValidationError: If the route or a vehicle is missing/unassignable, or
            the schedule config is malformed.
    """
    try:
        route = Route.objects.get(pk=route_id)
    except Route.DoesNotExist:
        raise ValidationError("Trajet introuvable.")

    if days <= 0:
        raise ValidationError("Le nombre de jours doit etre positif.")

    # Cache des vehicules pour eviter des requetes repetees.
    vehicle_cache: dict[int, Vehicle] = {}

    def _vehicle(vehicle_id: int) -> Vehicle:
        if vehicle_id not in vehicle_cache:
            try:
                vehicle = Vehicle.objects.get(pk=vehicle_id, company=route.company)
            except Vehicle.DoesNotExist:
                raise ValidationError(f"Vehicule {vehicle_id} introuvable.")
            ensure_vehicle_assignable(vehicle)
            vehicle_cache[vehicle_id] = vehicle
        return vehicle_cache[vehicle_id]

    created: list[Trip] = []
    today = timezone.localdate()
    current_tz = timezone.get_current_timezone()

    for offset in range(days):
        day = today + timedelta(days=offset)
        for slot in schedule_config:
            weekdays = slot.get("days") or []
            if day.weekday() not in weekdays:
                continue

            vehicle = _vehicle(slot["vehicle_id"])
            slot_time = _parse_time(slot["time"])
            departure = timezone.make_aware(
                datetime.combine(day, slot_time), current_tz
            )
            trip = Trip.objects.create(
                route=route,
                vehicle=vehicle,
                departure_time=departure,
                price=route.base_price,
                available_seats=vehicle.total_seats,
            )
            created.append(trip)

    return created


def _passenger_phones(trip: Trip) -> list[str]:
    """Collect distinct passenger phone numbers for a trip's active bookings.

    Resilient to the bookings app not being wired yet (PROMPT 05): if the
    ``bookings`` reverse relation is absent, an empty list is returned.

    Args:
        trip: The trip whose passengers are listed.

    Returns:
        Ordered list of unique phone numbers.
    """
    bookings = getattr(trip, "bookings", None)
    if bookings is None:
        return []

    phones = (
        bookings.exclude(status="cancelled")
        .values_list("phone", flat=True)
        .distinct()
    )
    return [phone for phone in phones if phone]


@transaction.atomic
def cancel_trip(trip: Trip, reason: str) -> Trip:
    """Cancel a trip and notify every booked passenger by SMS.

    Args:
        trip: The trip to cancel.
        reason: Plain-text reason stored on the trip and sent to passengers.

    Returns:
        The updated trip.

    Raises:
        ValidationError: If the trip is already cancelled or completed.
    """
    if trip.status in {Trip.TripStatus.CANCELLED, Trip.TripStatus.COMPLETED}:
        raise ValidationError(
            "Un voyage annule ou termine ne peut pas etre annule."
        )

    trip.status = Trip.TripStatus.CANCELLED
    trip.cancellation_reason = reason
    trip.save(update_fields=["status", "cancellation_reason", "updated_at"])

    message = (
        f"Votre voyage {trip.route} du "
        f"{timezone.localtime(trip.departure_time):%d/%m/%Y a %Hh%M} "
        f"est annule. Motif : {reason}"
    )
    for phone in _passenger_phones(trip):
        send_sms(phone, message)

    return trip
