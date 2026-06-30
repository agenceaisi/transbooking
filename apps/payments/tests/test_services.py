from decimal import Decimal

import pytest

from apps.bookings.models import BookingStatus
from apps.bookings.tests.factories import BookingFactory
from apps.payments.exceptions import (
    BookingAlreadyPaid,
    PaymentAlreadyConfirmed,
    TransactionRefRequired,
)
from apps.payments.models import PaymentMethod, PaymentStatus
from apps.payments.services import (
    compute_commission,
    confirm_payment,
    generate_receipt_pdf,
    initiate_payment,
)

from .factories import PaymentFactory


@pytest.fixture(autouse=True)
def _mute_sms(monkeypatch):
    monkeypatch.setattr("apps.payments.services.send_sms", lambda *a, **k: None)


@pytest.mark.django_db
def test_initiate_payment_creates_pending_payment():
    booking = BookingFactory(status=BookingStatus.PENDING, amount=5000)

    payment = initiate_payment(booking, method=PaymentMethod.ORANGE_MONEY, phone="+22670000001")

    assert payment.status == PaymentStatus.PENDING
    assert payment.amount == booking.amount
    assert payment.booking == booking


@pytest.mark.django_db
def test_initiate_payment_rejects_already_paid_booking():
    booking = BookingFactory(status=BookingStatus.PAID)
    with pytest.raises(BookingAlreadyPaid):
        initiate_payment(booking, method=PaymentMethod.CASH)


@pytest.mark.django_db
def test_confirm_payment_marks_booking_paid():
    booking = BookingFactory(status=BookingStatus.PENDING)
    payment = PaymentFactory(booking=booking, method=PaymentMethod.CASH)

    payment = confirm_payment(payment)

    booking.refresh_from_db()
    assert payment.status == PaymentStatus.PAID
    assert payment.paid_at is not None
    assert payment.receipt_url
    assert booking.status == BookingStatus.PAID


@pytest.mark.django_db
def test_confirm_mobile_money_requires_transaction_ref():
    payment = PaymentFactory(method=PaymentMethod.MOOV_MONEY)
    with pytest.raises(TransactionRefRequired):
        confirm_payment(payment, transaction_ref="")


@pytest.mark.django_db
def test_confirm_payment_is_idempotent():
    payment = PaymentFactory(method=PaymentMethod.CASH)
    confirm_payment(payment)
    payment.refresh_from_db()
    with pytest.raises(PaymentAlreadyConfirmed):
        confirm_payment(payment)


@pytest.mark.django_db
def test_confirm_payment_freezes_commission():
    booking = BookingFactory(status=BookingStatus.PENDING, amount=Decimal("10000"))
    booking.trip.route.company.commission_rate = Decimal("8.00")
    booking.trip.route.company.save(update_fields=["commission_rate"])
    payment = PaymentFactory(booking=booking, amount=Decimal("10000"), method=PaymentMethod.CASH)

    payment = confirm_payment(payment)

    assert payment.commission == Decimal("800.00")


@pytest.mark.django_db
def test_compute_commission_falls_back_to_default(settings):
    settings.COMMISSION_RATE_DEFAULT = 10.0
    assert compute_commission(Decimal("5000"), company=None) == Decimal("500.00")


@pytest.mark.django_db
def test_generate_receipt_pdf_returns_pdf_bytes():
    payment = confirm_payment(PaymentFactory(method=PaymentMethod.CASH))
    pdf = generate_receipt_pdf(payment)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"
