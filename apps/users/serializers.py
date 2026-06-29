from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from utils.validators import validate_phone_bf

from .models import AgentProfile, User
from .services import create_voyageur


class UserRegistrationSerializer(serializers.Serializer):
    prenom = serializers.CharField(max_length=100)
    nom = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=30, validators=[validate_phone_bf])
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)

    def validate_phone(self, value: str) -> str:
        phone = value.strip()
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("Ce numero de telephone est deja utilise.")
        return phone

    def create(self, validated_data: dict) -> User:
        try:
            return create_voyageur(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class UserProfileSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["prenom", "nom", "phone", "email", "role"]

    def get_role(self, obj: User) -> str | None:
        return obj.role.name if obj.role_id else None


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["phone", "email"]

    def validate_phone(self, value: str) -> str:
        phone = value.strip()
        queryset = User.objects.filter(phone=phone)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Ce numero de telephone est deja utilise.")
        return phone


class AgentProfileSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    company_name = serializers.SerializerMethodField()
    station_info = serializers.SerializerMethodField()
    vehicle_info = serializers.SerializerMethodField()

    class Meta:
        model = AgentProfile
        fields = [
            "user",
            "agent_type",
            "company_name",
            "station_info",
            "vehicle_info",
        ]

    def get_company_name(self, obj: AgentProfile) -> str | None:
        return obj.company.name if obj.company_id else None

    def get_station_info(self, obj: AgentProfile) -> dict | None:
        if not obj.station_id:
            return None
        return {
            "id": obj.station_id,
            "name": obj.station.name,
            "city": obj.station.city.name,
        }

    def get_vehicle_info(self, obj: AgentProfile) -> dict | None:
        if not obj.vehicle_id:
            return None
        return {
            "id": obj.vehicle_id,
            "registration": obj.vehicle.registration,
            "total_seats": obj.vehicle.total_seats,
        }


class TransBookingTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        data["role"] = self.user.role.name if self.user.role_id else None
        data["prenom"] = self.user.prenom
        return data
