from rest_framework import status
from rest_framework.exceptions import APIException


class PaymentAlreadyConfirmed(APIException):
    """Le paiement est deja confirme (HTTP 409)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Ce paiement est deja confirme."
    default_code = "payment_already_confirmed"


class TransactionRefRequired(APIException):
    """Reference de transaction manquante pour un paiement non especes (HTTP 400)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Reference de transaction requise hors especes."
    default_code = "transaction_ref_required"


class BookingAlreadyPaid(APIException):
    """La reservation est deja reglee (HTTP 409)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Cette reservation est deja reglee."
    default_code = "booking_already_paid"
