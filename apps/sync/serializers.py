from rest_framework import serializers

from apps.bookings.models import Booking
from apps.parcels.models import Parcel
from apps.trips.models import Trip

from .models import SyncConflict, SyncLog


# --------------------------------------------------------------------------- #
# Payload de synchronisation (entree)
# --------------------------------------------------------------------------- #


class OfflineBookingSerializer(serializers.Serializer):
    """Reservation saisie hors ligne par un agent guichet.

    Le `ticket_number` est genere localement par l'agent ; il sert de cle
    d'idempotence cote serveur (cf. business_rules.md §6).
    """

    ticket_number = serializers.CharField(max_length=20)
    trip_id = serializers.IntegerField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=30)
    seat_number = serializers.CharField(
        max_length=10, required=False, allow_blank=True
    )
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )
    payment_method = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    offline_created_at = serializers.DateTimeField()


class OfflineParcelSerializer(serializers.Serializer):
    """Colis enregistre hors ligne par un agent guichet."""

    tracking_number = serializers.CharField(max_length=20)
    origin_city = serializers.IntegerField()
    destination_city = serializers.IntegerField()
    destination_station = serializers.IntegerField(required=False, allow_null=True)
    trip = serializers.IntegerField(required=False, allow_null=True)
    sender_name = serializers.CharField(max_length=150)
    sender_phone = serializers.CharField(max_length=30)
    recipient_name = serializers.CharField(max_length=150)
    recipient_phone = serializers.CharField(max_length=30)
    description = serializers.CharField(required=False, allow_blank=True)
    weight_kg = serializers.DecimalField(max_digits=7, decimal_places=2)
    offline_created_at = serializers.DateTimeField()


class OfflineValidationSerializer(serializers.Serializer):
    """Embarquement valide hors ligne par un controleur."""

    ticket_number = serializers.CharField(max_length=20)
    offline_created_at = serializers.DateTimeField()


class SyncPayloadSerializer(serializers.Serializer):
    """Corps de `POST /api/v1/agent/sync/` : lots a synchroniser."""

    bookings = OfflineBookingSerializer(many=True, required=False, default=list)
    parcels = OfflineParcelSerializer(many=True, required=False, default=list)
    validations = OfflineValidationSerializer(many=True, required=False, default=list)


# --------------------------------------------------------------------------- #
# Lecture (sortie)
# --------------------------------------------------------------------------- #


class SyncConflictSerializer(serializers.ModelSerializer):
    """Lecture d'un conflit de synchronisation."""

    conflict_type_display = serializers.CharField(
        source="get_conflict_type_display", read_only=True
    )

    class Meta:
        model = SyncConflict
        fields = [
            "id",
            "entity",
            "conflict_type",
            "conflict_type_display",
            "reference",
            "original_seat",
            "assigned_seat",
            "resolution",
            "resolved",
            "created_at",
        ]


class SyncLogSerializer(serializers.ModelSerializer):
    """Lecture d'un journal de synchronisation avec ses conflits."""

    conflicts = SyncConflictSerializer(many=True, read_only=True)

    class Meta:
        model = SyncLog
        fields = [
            "id",
            "bookings_synced",
            "parcels_synced",
            "validations_synced",
            "conflicts_count",
            "errors_count",
            "conflicts",
            "created_at",
        ]


class SyncResultSerializer(serializers.Serializer):
    """Reponse de `POST /api/v1/agent/sync/` (cf. business_rules.md §6)."""

    synced = serializers.SerializerMethodField()
    conflicts = serializers.SerializerMethodField()
    errors = serializers.SerializerMethodField()

    def get_synced(self, log: SyncLog) -> dict:
        return {
            "bookings": log.bookings_synced,
            "parcels": log.parcels_synced,
            "validations": log.validations_synced,
        }

    def get_conflicts(self, log: SyncLog) -> list:
        return getattr(log, "synced_conflicts", [])

    def get_errors(self, log: SyncLog) -> list:
        return getattr(log, "synced_errors", [])


# --------------------------------------------------------------------------- #
# Donnees du mode hors ligne
# --------------------------------------------------------------------------- #


class OfflineTripSerializer(serializers.ModelSerializer):
    """Voyage du jour expose pour le travail hors ligne."""

    origin_city = serializers.CharField(source="route.origin_city.name", read_only=True)
    destination_city = serializers.CharField(
        source="route.destination_city.name", read_only=True
    )
    vehicle = serializers.CharField(source="vehicle.registration", read_only=True)
    seat_plan = serializers.JSONField(source="vehicle.seat_plan", read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id",
            "origin_city",
            "destination_city",
            "departure_time",
            "available_seats",
            "vehicle",
            "seat_plan",
            "status",
        ]


class OfflineBookingReadSerializer(serializers.ModelSerializer):
    """Reservation embarquee dans le paquet hors ligne (donnees minimales)."""

    passenger_name = serializers.CharField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            "ticket_number",
            "trip_id",
            "passenger_name",
            "phone",
            "seat_number",
            "qr_code",
            "status",
        ]


class OfflineParcelReadSerializer(serializers.ModelSerializer):
    """Colis en attente de remise expose pour le travail hors ligne."""

    destination_city = serializers.CharField(
        source="destination_city.name", read_only=True
    )

    class Meta:
        model = Parcel
        fields = [
            "tracking_number",
            "recipient_name",
            "recipient_phone",
            "destination_city",
            "status",
        ]
