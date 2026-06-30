from decimal import Decimal

from rest_framework import serializers

from apps.geography.models import City, Station
from apps.trips.models import Trip

from .models import NotificationMethod, Parcel, ParcelNotification, ParcelStatus


def _mask_phone(phone: str) -> str:
    """Mask all but the last two digits of a phone number for public display."""
    if not phone:
        return ""
    visible = phone[-2:]
    return f"{'*' * max(len(phone) - 2, 0)}{visible}"


class ParcelNotificationSerializer(serializers.ModelSerializer):
    """Lecture d'une notification colis."""

    method_display = serializers.CharField(source="get_method_display", read_only=True)

    class Meta:
        model = ParcelNotification
        fields = ["id", "method", "method_display", "message", "created_at"]


class ParcelHistoryMixin:
    """Construit l'historique d'un colis a partir de ses evenements connus."""

    def get_history(self, parcel: Parcel) -> list:
        events = [
            {
                "event": "registered",
                "label": "Colis enregistre",
                "timestamp": parcel.created_at,
            }
        ]
        for notification in parcel.notifications.all():
            events.append(
                {
                    "event": f"notified_{notification.method}",
                    "label": notification.get_method_display(),
                    "timestamp": notification.created_at,
                }
            )
        if parcel.collected_at:
            events.append(
                {
                    "event": "collected",
                    "label": "Colis remis",
                    "timestamp": parcel.collected_at,
                }
            )
        return sorted(events, key=lambda event: event["timestamp"])


class ParcelTrackSerializer(ParcelHistoryMixin, serializers.ModelSerializer):
    """Suivi public d'un colis : statut + historique, sans donnees sensibles."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    origin_city = serializers.CharField(source="origin_city.name", read_only=True)
    destination_city = serializers.CharField(
        source="destination_city.name", read_only=True
    )
    recipient_phone = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    class Meta:
        model = Parcel
        fields = [
            "tracking_number",
            "status",
            "status_display",
            "origin_city",
            "destination_city",
            "recipient_name",
            "recipient_phone",
            "history",
        ]

    def get_recipient_phone(self, parcel: Parcel) -> str:
        return _mask_phone(parcel.recipient_phone)


class ParcelReadSerializer(ParcelHistoryMixin, serializers.ModelSerializer):
    """Lecture detaillee d'un colis (agent, admin) avec historique complet."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    origin_city = serializers.CharField(source="origin_city.name", read_only=True)
    destination_city = serializers.CharField(
        source="destination_city.name", read_only=True
    )
    notifications = ParcelNotificationSerializer(many=True, read_only=True)
    history = serializers.SerializerMethodField()

    class Meta:
        model = Parcel
        fields = [
            "id",
            "tracking_number",
            "company",
            "trip",
            "origin_city",
            "destination_city",
            "origin_station",
            "destination_station",
            "sender_name",
            "sender_phone",
            "recipient_name",
            "recipient_phone",
            "description",
            "weight_kg",
            "tariff",
            "qr_code",
            "status",
            "status_display",
            "collected_at",
            "is_offline",
            "notifications",
            "history",
            "created_at",
            "updated_at",
        ]


class AgentParcelCreateSerializer(serializers.Serializer):
    """Enregistrement d'un colis au guichet (mode hors ligne supporte).

    La compagnie et la gare de depart sont deduites du profil agent dans la vue.
    Le tarif et le `tracking_number` sont calcules par le service, jamais fournis
    par le client (sauf `tracking_number` en mode hors ligne).
    """

    origin_city = serializers.PrimaryKeyRelatedField(queryset=City.objects.all())
    destination_city = serializers.PrimaryKeyRelatedField(queryset=City.objects.all())
    destination_station = serializers.PrimaryKeyRelatedField(
        queryset=Station.objects.all(), required=False, allow_null=True
    )
    trip = serializers.PrimaryKeyRelatedField(
        queryset=Trip.objects.all(), required=False, allow_null=True
    )
    sender_name = serializers.CharField()
    sender_phone = serializers.CharField()
    recipient_name = serializers.CharField()
    recipient_phone = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    weight_kg = serializers.DecimalField(
        max_digits=7, decimal_places=2, min_value=Decimal("0.1")
    )
    tracking_number = serializers.CharField(required=False, allow_blank=True)
    is_offline = serializers.BooleanField(required=False, default=False)
    offline_created_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs["origin_city"] == attrs["destination_city"]:
            raise serializers.ValidationError(
                "La ville de depart et la ville d'arrivee doivent differer."
            )
        if attrs.get("is_offline") and not attrs.get("offline_created_at"):
            raise serializers.ValidationError(
                {"offline_created_at": "Date de saisie hors ligne requise."}
            )
        return attrs


class ParcelStatusSerializer(serializers.Serializer):
    """Changement manuel du statut d'un colis (admin compagnie)."""

    status = serializers.ChoiceField(choices=ParcelStatus.choices)


class ParcelUpdateSerializer(serializers.ModelSerializer):
    """Mise a jour partielle des infos d'un colis (admin compagnie)."""

    class Meta:
        model = Parcel
        fields = [
            "recipient_name",
            "recipient_phone",
            "sender_name",
            "sender_phone",
            "description",
            "destination_station",
            "trip",
        ]


class NotifySerializer(serializers.Serializer):
    """Parametre de la notification destinataire (SMS ou appel manuel)."""

    method = serializers.ChoiceField(
        choices=NotificationMethod.choices,
        required=False,
        default=NotificationMethod.SMS,
    )
