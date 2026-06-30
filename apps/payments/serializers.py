from rest_framework import serializers

from apps.bookings.models import Booking

from .models import Payment, PaymentMethod


class PaymentReadSerializer(serializers.ModelSerializer):
    """Lecture du statut d'un paiement (voyageur, agent, admin)."""

    method_display = serializers.CharField(source="get_method_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    ticket_number = serializers.CharField(
        source="booking.ticket_number", read_only=True, default=None
    )
    transaction_ref = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "ticket_number",
            "amount",
            "method",
            "method_display",
            "status",
            "status_display",
            "transaction_ref",
            "phone",
            "receipt_url",
            "paid_at",
            "created_at",
        ]

    def get_transaction_ref(self, payment: Payment) -> str:
        # Donnee sensible : on ne renvoie que les 4 derniers caracteres.
        ref = payment.transaction_ref
        if not ref:
            return ""
        return f"****{ref[-4:]}" if len(ref) > 4 else "****"


class PaymentInitiateSerializer(serializers.Serializer):
    """Initiation d'un paiement par un voyageur (booking + moyen).

    Le paiement reste `pending` jusqu'a confirmation (Mobile Money manuel).
    """

    booking_id = serializers.PrimaryKeyRelatedField(
        queryset=Booking.objects.all(), source="booking", required=False
    )
    parcel_id = serializers.IntegerField(required=False)
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    phone = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs.get("parcel_id") is not None:
            # TODO: supporter le paiement de colis quand apps.parcels sera dispo.
            raise serializers.ValidationError(
                {"parcel_id": "Le paiement de colis n'est pas encore disponible."}
            )
        if attrs.get("booking") is None:
            raise serializers.ValidationError(
                {"booking_id": "Champ requis : booking_id."}
            )
        return attrs


class PaymentVerifySerializer(serializers.Serializer):
    """Confirmation d'un paiement (saisie de la reference de transaction)."""

    transaction_ref = serializers.CharField(required=False, allow_blank=True, default="")


class AgentPaymentSerializer(serializers.Serializer):
    """Encaissement au guichet (especes ou Mobile Money) — initie et confirme."""

    booking_id = serializers.PrimaryKeyRelatedField(
        queryset=Booking.objects.all(), source="booking"
    )
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    transaction_ref = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["method"] != PaymentMethod.CASH and not attrs.get("transaction_ref"):
            raise serializers.ValidationError(
                {"transaction_ref": "Reference de transaction requise hors especes."}
            )
        return attrs
