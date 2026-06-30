from rest_framework import serializers

from apps.trips.models import Trip

from .models import BoardingValidation, Booking, BookingStatus


class TripSummarySerializer(serializers.ModelSerializer):
    """Resume d'un voyage embarque dans le detail d'une reservation."""

    origin_city = serializers.CharField(source="route.origin_city.name", read_only=True)
    destination_city = serializers.CharField(
        source="route.destination_city.name", read_only=True
    )

    class Meta:
        model = Trip
        fields = [
            "id",
            "origin_city",
            "destination_city",
            "departure_time",
            "arrival_time",
            "status",
        ]


class BookingReadSerializer(serializers.ModelSerializer):
    """Lecture detaillee d'une reservation (voyageur, agent, admin)."""

    trip = TripSummarySerializer(read_only=True)
    passenger_name = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_boarded = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "ticket_number",
            "trip",
            "first_name",
            "last_name",
            "passenger_name",
            "phone",
            "seat_number",
            "amount",
            "payment_method",
            "qr_code",
            "status",
            "status_display",
            "is_offline",
            "is_boarded",
            "created_at",
            "updated_at",
        ]

    def get_is_boarded(self, booking: Booking) -> bool:
        return hasattr(booking, "boarding_validation")


class BookingCreateSerializer(serializers.Serializer):
    """Creation d'une reservation par un voyageur authentifie.

    L'identite du passager reprend par defaut le compte voyageur. Le siege est
    auto-attribue si non fourni. La reservation est creee au statut `pending`
    (paiement a confirmer).
    """

    trip = serializers.PrimaryKeyRelatedField(queryset=Trip.objects.all())
    seat_number = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)

    def validate_trip(self, trip: Trip) -> Trip:
        if trip.status in {Trip.TripStatus.CANCELLED, Trip.TripStatus.COMPLETED}:
            raise serializers.ValidationError(
                "Ce voyage n'est plus ouvert a la reservation."
            )
        return trip

    def to_internal_value(self, data):
        attrs = super().to_internal_value(data)
        user = self.context["request"].user
        attrs.setdefault("first_name", user.prenom)
        attrs.setdefault("last_name", user.nom)
        if not attrs.get("phone"):
            attrs["phone"] = user.phone
        attrs["user"] = user
        attrs["amount"] = attrs["trip"].price
        attrs["status"] = BookingStatus.PENDING
        return attrs


class AgentBookingCreateSerializer(serializers.Serializer):
    """Enregistrement d'un passager au guichet (mode hors ligne supporte).

    L'agent encaisse au guichet : la reservation est creee au statut `paid`.
    `transaction_ref` est requis pour les paiements non-especes.
    """

    trip = serializers.PrimaryKeyRelatedField(queryset=Trip.objects.all())
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    phone = serializers.CharField()
    seat_number = serializers.CharField(required=False, allow_blank=True)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )
    payment_method = serializers.CharField()
    transaction_ref = serializers.CharField(required=False, allow_blank=True)
    ticket_number = serializers.CharField(required=False, allow_blank=True)
    is_offline = serializers.BooleanField(required=False, default=False)
    offline_created_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_trip(self, trip: Trip) -> Trip:
        if trip.status in {Trip.TripStatus.CANCELLED, Trip.TripStatus.COMPLETED}:
            raise serializers.ValidationError(
                "Ce voyage n'est plus ouvert a la reservation."
            )
        return trip

    def validate(self, attrs):
        method = attrs.get("payment_method")
        if method and method != "cash" and not attrs.get("transaction_ref"):
            raise serializers.ValidationError(
                {"transaction_ref": "Reference de transaction requise hors especes."}
            )
        if attrs.get("is_offline") and not attrs.get("offline_created_at"):
            raise serializers.ValidationError(
                {"offline_created_at": "Date de saisie hors ligne requise."}
            )
        return attrs

    def to_internal_value(self, data):
        attrs = super().to_internal_value(data)
        attrs.setdefault("amount", attrs["trip"].price)
        attrs["status"] = BookingStatus.PAID
        attrs.pop("transaction_ref", None)
        return attrs


class BoardingValidationSerializer(serializers.ModelSerializer):
    """Lecture d'un embarquement."""

    ticket_number = serializers.CharField(
        source="booking.ticket_number", read_only=True
    )
    passenger_name = serializers.CharField(
        source="booking.passenger_name", read_only=True
    )
    method_display = serializers.CharField(source="get_method_display", read_only=True)

    class Meta:
        model = BoardingValidation
        fields = [
            "id",
            "ticket_number",
            "passenger_name",
            "method",
            "method_display",
            "boarded_at",
            "is_offline",
        ]
