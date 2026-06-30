import logging
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.bookings.models import Booking, BookingStatus
from utils.sms import send_sms

from .exceptions import (
    BookingAlreadyPaid,
    PaymentAlreadyConfirmed,
    TransactionRefRequired,
)
from .models import Payment, PaymentMethod, PaymentStatus

logger = logging.getLogger(__name__)


def _mask_ref(ref: str) -> str:
    """Mask a transaction reference for safe logging.

    Keeps only the last 4 characters visible (cf. security.md §sensitive data).

    Args:
        ref: The raw transaction reference.

    Returns:
        The masked reference (e.g. ``****1234``), or an empty string.
    """
    if not ref:
        return ""
    return f"****{ref[-4:]}" if len(ref) > 4 else "****"


def compute_commission(amount: Decimal, company) -> Decimal:
    """Compute the platform commission for a paid amount.

    Uses the company's ``commission_rate`` when set, otherwise the platform
    default ``COMMISSION_RATE_DEFAULT`` (cf. business_rules.md §2).

    Args:
        amount: The booking amount.
        company: The company owning the route, or ``None``.

    Returns:
        The commission, quantised to 2 decimal places.
    """
    rate = getattr(company, "commission_rate", None)
    if rate is None:
        rate = Decimal(str(settings.COMMISSION_RATE_DEFAULT))
    commission = (Decimal(amount) * Decimal(rate)) / Decimal("100")
    return commission.quantize(Decimal("0.01"))


def initiate_payment(booking: Booking, method: str, phone: str = "", agent=None) -> Payment:
    """Create a pending payment for a booking.

    Mobile Money is manual for now: the payment stays ``pending`` until an agent
    confirms it with a transaction reference (cf. business_rules.md §2).

    Args:
        booking: The booking to pay for.
        method: One of ``PaymentMethod`` values.
        phone: The payer phone number (Mobile Money), optional.
        agent: The agent recording the payment, or ``None`` online.

    Returns:
        The created payment.

    Raises:
        BookingAlreadyPaid: If the booking is already paid.

    # TODO: accepter aussi un colis (parcels.Parcel) quand le module sera dispo.
    """
    if booking.status == BookingStatus.PAID:
        raise BookingAlreadyPaid()

    payment = Payment.objects.create(
        booking=booking,
        amount=booking.amount,
        method=method,
        phone=phone or "",
        agent=agent,
        status=PaymentStatus.PENDING,
    )
    logger.info("Paiement %s initie pour le billet %s", payment.pk, booking.ticket_number)
    return payment


def confirm_payment(payment: Payment, transaction_ref: str = "") -> Payment:
    """Confirm a payment and mark its booking as paid.

    For Mobile Money / card the ``transaction_ref`` supplied by the agent is
    mandatory. The seat is already reserved at booking creation
    (cf. apps.bookings.services.create_booking, which decrements
    ``trip.available_seats`` under a row lock), so confirmation only flips the
    booking status to ``paid`` and freezes the platform commission.

    Args:
        payment: The pending payment to confirm.
        transaction_ref: The Mobile Money / card transaction reference.

    Returns:
        The updated payment.

    Raises:
        PaymentAlreadyConfirmed: If the payment is already paid.
        TransactionRefRequired: If a non-cash payment lacks a transaction ref.
    """
    if payment.status == PaymentStatus.PAID:
        raise PaymentAlreadyConfirmed()

    if payment.method != PaymentMethod.CASH and not transaction_ref:
        raise TransactionRefRequired()

    with transaction.atomic():
        # Verrou ligne sur le paiement : serialise une double confirmation.
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == PaymentStatus.PAID:
            raise PaymentAlreadyConfirmed()

        booking = payment.booking
        if booking is not None:
            company = booking.trip.route.company
            payment.commission = compute_commission(payment.amount, company)
            # La reservation passe a paye (le siege est deja reserve a la creation).
            booking.status = BookingStatus.PAID
            booking.payment_method = payment.method
            booking.save(update_fields=["status", "payment_method", "updated_at"])

        payment.transaction_ref = transaction_ref
        payment.status = PaymentStatus.PAID
        payment.paid_at = timezone.now()
        payment.receipt_url = f"/api/v1/payments/{payment.pk}/receipt/"
        payment.save(
            update_fields=[
                "transaction_ref",
                "status",
                "paid_at",
                "receipt_url",
                "commission",
                "updated_at",
            ]
        )

    logger.info(
        "Paiement %s confirme (ref %s)", payment.pk, _mask_ref(transaction_ref)
    )
    _send_payment_sms(payment)
    if booking is not None:
        _schedule_booking_notifications(booking)
    return payment


# Delai avant le depart pour l'envoi du SMS de rappel (cf. PROMPT 12).
REMINDER_HOURS_BEFORE = 3


def _schedule_booking_notifications(booking) -> None:
    """Trigger the confirmation SMS and schedule the departure reminder.

    Sends the booking confirmation asynchronously and books the departure
    reminder for ~3h before the trip via ``apply_async(eta=...)`` (skipped when
    the trip already departs within that window).

    Args:
        booking: The paid booking to notify.
    """
    # Import local : evite un cycle d'import bookings <-> payments au chargement.
    from datetime import timedelta

    from apps.bookings.tasks import (
        send_booking_confirmation_sms,
        send_departure_reminder_sms,
    )

    send_booking_confirmation_sms.delay(booking.pk)

    reminder_eta = booking.trip.departure_time - timedelta(hours=REMINDER_HOURS_BEFORE)
    if reminder_eta > timezone.now():
        send_departure_reminder_sms.apply_async(args=[booking.pk], eta=reminder_eta)


def _send_payment_sms(payment: Payment) -> None:
    """Send the payment confirmation SMS to the passenger.

    Args:
        payment: The confirmed payment.
    """
    booking = payment.booking
    if booking is None:
        return
    message = (
        f"Paiement confirme. Billet {booking.ticket_number}, "
        f"montant {payment.amount} FCFA. Bon voyage."
    )
    send_sms(booking.phone, message)


def generate_receipt_pdf(payment: Payment) -> bytes:
    """Render a payment receipt as a PDF document.

    Contains the transaction number, amount, date, company, trip, passenger and
    the booking QR code (cf. business_rules.md §2).

    Args:
        payment: The payment to render.

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

    booking = payment.booking

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(15 * mm, height - 18 * mm, "TransBooking BF - Recu")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(15 * mm, height - 24 * mm, f"Recu N : PAY{payment.pk:06d}")

    lines = [
        f"Date : {timezone.localtime(payment.paid_at or payment.created_at):%d/%m/%Y %Hh%M}",
        f"Montant : {payment.amount} FCFA",
        f"Moyen : {payment.get_method_display()}",
        f"Reference : {payment.transaction_ref or '-'}",
    ]
    if booking is not None:
        route = booking.trip.route
        lines.extend(
            [
                f"Compagnie : {route.company.name}",
                f"Trajet : {route.origin_city.name} -> {route.destination_city.name}",
                f"Passager : {booking.passenger_name}",
                f"Billet : {booking.ticket_number}",
            ]
        )

    y = height - 32 * mm
    pdf.setFont("Helvetica", 9)
    for line in lines:
        pdf.drawString(15 * mm, y, line)
        y -= 6 * mm

    if booking is not None and booking.qr_code:
        try:
            qr_image = ImageReader(BytesIO(base64.b64decode(booking.qr_code)))
            pdf.drawImage(
                qr_image,
                width - 40 * mm,
                12 * mm,
                width=25 * mm,
                height=25 * mm,
            )
        except Exception:
            # Un QR illisible ne doit pas casser la generation du recu.
            pass

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
