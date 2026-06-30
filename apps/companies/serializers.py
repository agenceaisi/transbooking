from rest_framework import serializers

from .models import (
    Company,
    CompanyNotificationSettings,
    CompanyPaymentMethod,
    CompanyStatus,
)


class CompanyPublicSerializer(serializers.ModelSerializer):
    """Fiche publique d'une compagnie (page d'accueil, recherche)."""

    logo = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = ["id", "name", "sigle", "logo", "description", "city", "rating"]

    def get_logo(self, obj: Company) -> str | None:
        if not obj.logo:
            return None
        request = self.context.get("request")
        url = obj.logo.url
        return request.build_absolute_uri(url) if request else url

    def get_rating(self, obj: Company) -> float | None:
        # `avg_rating` est annote par la vue quand l'app reviews est disponible.
        avg = getattr(obj, "avg_rating", None)
        return round(avg, 1) if avg is not None else None


class CompanyPublicDetailSerializer(CompanyPublicSerializer):
    """Fiche publique detaillee : ajoute contact et avis."""

    reviews = serializers.SerializerMethodField()

    class Meta(CompanyPublicSerializer.Meta):
        fields = CompanyPublicSerializer.Meta.fields + ["phone", "email", "reviews"]

    def get_reviews(self, obj: Company) -> list:
        # TODO: brancher sur l'app reviews (PROMPT 08) une fois disponible.
        return []


class CompanyPaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyPaymentMethod
        fields = ["method", "is_active"]


class CompanyNotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyNotificationSettings
        fields = [
            "sms_booking_confirmation",
            "sms_departure_reminder",
            "sms_parcel_arrival",
        ]


class CompanyDetailSerializer(serializers.ModelSerializer):
    """Vue complete pour le super admin et le company admin."""

    active_payment_methods = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "sigle",
            "description",
            "logo",
            "banner",
            "primary_color",
            "welcome_message",
            "city",
            "address",
            "phone",
            "email",
            "responsible_name",
            "responsible_phone",
            "rccm",
            "ifu",
            "commission_rate",
            "status",
            "rejection_reason",
            "suspension_reason",
            "active_payment_methods",
            "subscription_status",
            "created_at",
            "updated_at",
        ]

    def get_active_payment_methods(self, obj: Company) -> list[str]:
        return [pm.method for pm in obj.payment_methods.all() if pm.is_active]

    def get_subscription_status(self, obj: Company) -> str | None:
        # Abonnement courant de la compagnie (OneToOne, peut etre absent).
        subscription = getattr(obj, "subscription", None)
        return getattr(subscription, "status", None) if subscription else None


class CompanyCreateSerializer(serializers.ModelSerializer):
    """Formulaire de creation d'une compagnie par le super admin."""

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "sigle",
            "description",
            "city",
            "address",
            "phone",
            "email",
            "responsible_name",
            "responsible_phone",
            "rccm",
            "ifu",
            "commission_rate",
            "status",
        ]
        read_only_fields = ["id", "status"]

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if Company.objects.filter(name__iexact=name).exists():
            raise serializers.ValidationError("Une compagnie porte deja ce nom.")
        return name

    def create(self, validated_data: dict) -> Company:
        # Une compagnie creee directement par le super admin est active d'emblee.
        validated_data["status"] = CompanyStatus.ACTIVE
        return super().create(validated_data)


class CompanySettingsSerializer(serializers.ModelSerializer):
    """Parametres editables par le company admin (charte graphique, accueil)."""

    class Meta:
        model = Company
        fields = [
            "name",
            "sigle",
            "description",
            "logo",
            "banner",
            "primary_color",
            "welcome_message",
            "address",
            "phone",
            "email",
            "responsible_name",
            "responsible_phone",
        ]
