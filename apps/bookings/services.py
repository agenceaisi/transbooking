from datetime import timedelta
from io import BytesIO

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.trips.models import Trip
from apps.vehicles.services import next_available_seat
from utils.qr import generate_qr
from utils.sms import send_sms

from .exceptions import (
    CancellationTooLate,
    SeatTaken,
    TripFull,
    TripUnavailable,
)
from .models import BoardingMethod, BoardingValidation, Booking, BookingStatus

# Roles autorises a annuler une reservation sans contrainte de delai.
_ADMIN_ROLES = {"company_admin", "super_admin"}
# Delai minimal entre l'annulation par un voyageur et le depart.
CANCELLATION_DEADLINE = timedelta(hours=2)


def generate_ticket_number() -> str:
    """Build the next ticket number: ``BF`` + year + 6-digit sequence.

    The sequence is scoped to the current calendar year (e.g. ``BF2026001234``).
    Call inside the booking transaction so the read of the last number and the
    insert are serialized by the trip row lock.

    Returns:
        The next available ticket number for the current year.
    """
    prefix = f"BF{timezone.now().year}"
    last = (
        Booking.objects.filter(ticket_number__startswith=prefix)
        .aggregate(last=Max("ticket_number"))
        .get("last")
    )
    sequence = int(last[len(prefix):]) + 1 if last else 1
    return f"{prefix}{sequence:06d}"


def create_booking(validated_data: dict, agent=None) -> Booking:
    """Create a booking, reserving a seat under a row-level trip lock.

    The trip row is locked with ``select_for_update()`` so concurrent requests
    cannot oversell seats. The seat is auto-assigned when none is supplied, the
    ticket number and QR code are generated, and a confirmation SMS is sent.

    Args:
        validated_data: Cleaned fields. Recognised keys: ``trip`` (Trip),
            ``first_name``, ``last_name``, ``phone``, ``amount``, ``status``,
            ``seat_number`` (optional), ``payment_method``, ``user`` (optional),
            ``is_offline``, ``offline_created_at``, ``ticket_number`` (offline).
        agent: The agent user registering the booking, or ``None`` online.

    Returns:
        The created booking.

    Raises:
        TripUnavailable: If the trip is cancelled or completed (HTTP 410).
        TripFull: If no seat is available (HTTP 409).
        SeatTaken: If the requested seat is already booked (HTTP 409).
    """
    trip_arg = validated_data["trip"]
    trip_id = trip_arg.id if isinstance(trip_arg, Trip) else trip_arg
    is_offline = validated_data.get("is_offline", False)

    with transaction.atomic():
        # Verrou ligne : serialise l'attribution des sieges (cf. business_rules §1).
        trip = Trip.objects.select_for_update().select_related("vehicle").get(pk=trip_id)

        if trip.status in {Trip.TripStatus.CANCELLED, Trip.TripStatus.COMPLETED}:
            raise TripUnavailable()
        if trip.available_seats <= 0:
            raise TripFull()

        seat_number = validated_data.get("seat_number")
        if not seat_number:
            # next_available_seat leve ValidationError si plus aucun siege libre.
            try:
                seat_number = next_available_seat(trip.vehicle, trip)
            except Exception:
                raise TripFull()

        ticket_number = validated_data.get("ticket_number") or generate_ticket_number()

        try:
            with transaction.atomic():
                booking = Booking.objects.create(
                    trip=trip,
                    user=validated_data.get("user"),
                    agent=agent,
                    first_name=validated_data["first_name"],
                    last_name=validated_data["last_name"],
                    phone=validated_data["phone"],
                    seat_number=seat_number,
                    amount=validated_data["amount"],
                    payment_method=validated_data.get("payment_method", ""),
                    ticket_number=ticket_number,
                    qr_code=generate_qr(ticket_number),
                    status=validated_data.get("status", BookingStatus.PENDING),
                    is_offline=is_offline,
                    offline_created_at=validated_data.get("offline_created_at"),
                    synced_at=None if is_offline else timezone.now(),
                )
        except IntegrityError:
            # Course sur un siege precis demande simultanement.
            raise SeatTaken()

        trip.available_seats -= 1
        trip.save(update_fields=["available_seats", "updated_at"])

    _send_confirmation_sms(booking)
    return booking


def _send_confirmation_sms(booking: Booking) -> None:
    """Send the booking confirmation SMS to the passenger.

    Args:
        booking: The booking to confirm.
    """
    message = (
        f"Reservation confirmee. Billet {booking.ticket_number}, "
        f"siege {booking.seat_number}. Voyage du "
        f"{timezone.localtime(booking.trip.departure_time):%d/%m/%Y a %Hh%M}."
    )
    send_sms(booking.phone, message)


def cancel_booking(booking: Booking, cancelled_by, reason: str = "") -> Booking:
    """Cancel a booking and free its seat.

    Voyageurs may only cancel until 2h before departure; company/super admins
    cancel without restriction (cf. business_rules.md §1).

    Args:
        booking: The booking to cancel.
        cancelled_by: The user requesting the cancellation.
        reason: Optional plain-text reason.

    Returns:
        The updated booking.

    Raises:
        CancellationTooLate: If a voyageur cancels within 2h of departure.
    """
    if booking.status == BookingStatus.CANCELLED:
        return booking

    role = getattr(getattr(cancelled_by, "role", None), "name", None)
    is_admin = role in _ADMIN_ROLES
    if not is_admin:
        deadline = booking.trip.departure_time - CANCELLATION_DEADLINE
        if timezone.now() >= deadline:
            raise CancellationTooLate()

    with transaction.atomic():
        trip = Trip.objects.select_for_update().get(pk=booking.trip_id)
        booking.status = BookingStatus.CANCELLED
        booking.cancellation_reason = reason
        booking.cancelled_by = cancelled_by
        booking.save(
            update_fields=[
                "status",
                "cancellation_reason",
                "cancelled_by",
                "updated_at",
            ]
        )
        # Le siege est libere et redevient reservable.
        trip.available_seats += 1
        trip.save(update_fields=["available_seats", "updated_at"])

    return booking


# Codes couleur renvoyes au controleur lors d'un scan (UI feu tricolore).
_SCAN_RESULTS = {
    BookingStatus.PAID: ("valid", "green", "Billet valide."),
    BookingStatus.PENDING: ("unpaid", "orange", "Paiement non confirme."),
    BookingStatus.CANCELLED: ("cancelled", "red", "Reservation annulee."),
    BookingStatus.REFUNDED: ("refunded", "red", "Reservation remboursee."),
}


def scan_qr(qr_data: str, agent) -> dict:
    """Resolve a scanned QR code to a colour-coded boarding status.

    Args:
        qr_data: The decoded QR payload (the ticket number).
        agent: The controleur scanning the ticket (multi-tenant scope).

    Returns:
        A dict with ``status``, ``color``, ``message`` and ``booking`` info.

    Raises:
        Booking.DoesNotExist: If no booking matches within the agent's company.
    """
    ticket_number = (qr_data or "").strip()
    queryset = Booking.objects.select_related(
        "trip__route__origin_city", "trip__route__destination_city"
    )
    profile = getattr(agent, "agent_profile", None)
    if profile is not None and profile.company_id is not None:
        # Isolation multi-tenant : un controleur ne scanne que sa compagnie.
        queryset = queryset.filter(trip__route__company_id=profile.company_id)

    # Leve Booking.DoesNotExist -> traduit en 404 par la vue.
    booking = queryset.get(ticket_number=ticket_number)

    already_boarded = BoardingValidation.objects.filter(booking=booking).exists()
    if already_boarded and booking.status == BookingStatus.PAID:
        status_code, color, message = (
            "already_boarded",
            "orange",
            "Passager deja embarque.",
        )
    else:
        status_code, color, message = _SCAN_RESULTS.get(
            booking.status, ("invalid", "red", "Billet invalide.")
        )

    return {
        "status": status_code,
        "color": color,
        "message": message,
        "booking": {
            "ticket_number": booking.ticket_number,
            "passenger_name": booking.passenger_name,
            "seat_number": booking.seat_number,
            "status": booking.status,
        },
    }


def check_in(booking: Booking, agent, method: str = BoardingMethod.MANUAL) -> BoardingValidation:
    """Record (or return) the boarding validation for a booking.

    Idempotent: a booking already boarded returns its existing validation.

    Args:
        booking: The booking to board.
        agent: The controleur performing the check-in.
        method: ``scan`` or ``manual``.

    Returns:
        The boarding validation.
    """
    validation, _ = BoardingValidation.objects.get_or_create(
        booking=booking,
        defaults={
            "validated_by": agent,
            "method": method,
            "boarded_at": timezone.now(),
        },
    )
    return validation


def generate_ticket_pdf(booking: Booking) -> bytes:
    """Render a booking ticket as a PDF document.

    Args:
        booking: The booking to render. Contains trip, seat and QR data.

    Returns:
        The PDF file content as bytes.
    """
    # Import local : ReportLab n'est requis que pour la generation PDF.
    import base64

    from reportlab.lib.pagesizes import A6
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    width, height = A6
    pdf = canvas.Canvas(buffer, pagesize=A6)

    trip = booking.trip
    route = trip.route

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(15 * mm, height - 18 * mm, "TransBooking BF")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(15 * mm, height - 24 * mm, f"Billet : {booking.ticket_number}")

    lines = [
        f"Passager : {booking.passenger_name}",
        f"Trajet : {route.origin_city.name} -> {route.destination_city.name}",
        f"Depart : {timezone.localtime(trip.departure_time):%d/%m/%Y a %Hh%M}",
        f"Siege : {booking.seat_number}",
        f"Montant : {booking.amount} FCFA",
        f"Statut : {booking.get_status_display()}",
    ]
    y = height - 34 * mm
    pdf.setFont("Helvetica", 9)
    for line in lines:
        pdf.drawString(15 * mm, y, line)
        y -= 6 * mm

    if booking.qr_code:
        try:
            qr_image = ImageReader(BytesIO(base64.b64decode(booking.qr_code)))
            pdf.drawImage(
                qr_image,
                width - 45 * mm,
                15 * mm,
                width=30 * mm,
                height=30 * mm,
            )
        except Exception:
            # Un QR illisible ne doit pas casser la generation du billet.
            pass

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
