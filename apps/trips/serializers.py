from rest_framework import serializers

from apps.vehicles.services import get_available_seats

from .models import Trip


class TripWriteSerializer(serializers.ModelSerializer):
    """Creation/modification d'un voyage par le company admin.

    `available_seats` est initialise depuis `vehicle.total_seats` a la creation
    et n'est jamais fixe manuellement. `price` reprend `route.base_price` si non
    fourni.
    """

    class Meta:
        model = Trip
        fields = [
            "id",
            "route",
            "vehicle",
            "departure_time",
            "arrival_time",
            "price",
            "status",
            "cancellation_reason",
        ]
        read_only_fields = ["id", "cancellation_reason"]
        extra_kwargs = {"price": {"required": False}}

    def validate(self, attrs):
        vehicle = attrs.get("vehicle", getattr(self.instance, "vehicle", None))
        route = attrs.get("route", getattr(self.instance, "route", None))
        if route and vehicle and route.company_id != vehicle.company_id:
            raise serializers.ValidationError(
                "Le vehicule et le trajet doivent appartenir a la meme compagnie."
            )
        return attrs

    def create(self, validated_data):
        vehicle = validated_data["vehicle"]
        validated_data.setdefault("price", validated_data["route"].base_price)
        validated_data["available_seats"] = vehicle.total_seats
        return super().create(validated_data)


class TripReadSerializer(serializers.ModelSerializer):
    """Lecture detaillee d'un voyage (admin, agent)."""

    route_label = serializers.SerializerMethodField()
    origin_city = serializers.CharField(source="route.origin_city.name", read_only=True)
    destination_city = serializers.CharField(
        source="route.destination_city.name", read_only=True
    )
    vehicle_registration = serializers.CharField(
        source="vehicle.registration", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id",
            "route",
            "route_label",
            "origin_city",
            "destination_city",
            "vehicle",
            "vehicle_registration",
            "departure_time",
            "arrival_time",
            "price",
            "available_seats",
            "status",
            "status_display",
            "created_at",
            "updated_at",
        ]

    def get_route_label(self, trip: Trip) -> str:
        return f"{trip.route.origin_city.name} - {trip.route.destination_city.name}"


class TripDetailSerializer(TripReadSerializer):
    """Detail public d'un voyage incluant la liste des sieges disponibles."""

    available_seat_numbers = serializers.SerializerMethodField()

    class Meta(TripReadSerializer.Meta):
        fields = TripReadSerializer.Meta.fields + ["available_seat_numbers"]

    def get_available_seat_numbers(self, trip: Trip) -> list[str]:
        return get_available_seats(trip.vehicle, trip)
