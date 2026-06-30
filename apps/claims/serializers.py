from rest_framework import serializers

from .models import Claim, ClaimStatus


class ClaimReadSerializer(serializers.ModelSerializer):
    """Lecture detaillee d'une reclamation (voyageur, admin, super admin)."""

    claim_type_display = serializers.CharField(
        source="get_claim_type_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    company_name = serializers.CharField(source="company.name", read_only=True)
    ticket_number = serializers.CharField(
        source="booking.ticket_number", read_only=True, default=None
    )
    # Annote par services.annotated_claims() — absent => False.
    is_overdue = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Claim
        fields = [
            "id",
            "company",
            "company_name",
            "booking",
            "ticket_number",
            "claim_type",
            "claim_type_display",
            "subject",
            "description",
            "status",
            "status_display",
            "response",
            "responded_at",
            "is_overdue",
            "created_at",
            "updated_at",
        ]


class ClaimCreateSerializer(serializers.ModelSerializer):
    """Depot d'une reclamation par un voyageur.

    La compagnie peut etre fournie directement ou deduite de la reservation
    referencee. La reservation doit appartenir au voyageur courant.
    """

    class Meta:
        model = Claim
        fields = ["company", "booking", "claim_type", "subject", "description"]
        extra_kwargs = {"company": {"required": False}}

    def validate_booking(self, booking):
        request = self.context.get("request")
        if booking is not None and request is not None:
            if booking.user_id != request.user.id:
                raise serializers.ValidationError(
                    "Cette reservation ne vous appartient pas."
                )
        return booking

    def validate(self, attrs):
        booking = attrs.get("booking")
        company = attrs.get("company")
        if booking is not None:
            # La compagnie est celle qui exploite le trajet de la reservation.
            attrs["company"] = booking.trip.route.company
        elif company is None:
            raise serializers.ValidationError(
                {"company": "La compagnie ou une reservation est obligatoire."}
            )
        return attrs


class ClaimRespondSerializer(serializers.Serializer):
    """Reponse d'un admin de compagnie a une reclamation."""

    response = serializers.CharField()
    status = serializers.ChoiceField(
        choices=[
            ClaimStatus.IN_PROGRESS,
            ClaimStatus.RESOLVED,
            ClaimStatus.CLOSED,
        ],
        default=ClaimStatus.RESOLVED,
    )
