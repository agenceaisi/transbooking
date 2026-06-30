from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from utils.permissions import IsAgent, IsCompanyAdmin

from .models import Trip
from .serializers import (
    TripDetailSerializer,
    TripReadSerializer,
    TripWriteSerializer,
)
from .services import cancel_trip, generate_trips


class CompanyTripViewSet(viewsets.ModelViewSet):
    """CRUD des voyages de la compagnie du company admin courant."""

    permission_classes = [IsCompanyAdmin]
    filterset_fields = ["route", "status"]

    def get_company(self):
        company = getattr(self.request.user, "administered_company", None)
        if company is None:
            raise NotFound("Aucune compagnie associee a cet utilisateur.")
        return company

    def get_queryset(self):
        return (
            Trip.objects.filter(route__company=self.get_company())
            .select_related("route__origin_city", "route__destination_city", "vehicle")
        )

    def get_serializer_class(self):
        if self.action in {"list", "retrieve"}:
            return TripReadSerializer
        return TripWriteSerializer

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        date = self.request.query_params.get("date")
        if date:
            queryset = queryset.filter(departure_time__date=date)
        return queryset

    def destroy(self, request, *args, **kwargs):
        # La suppression d'un voyage = annulation + notification des passagers.
        trip = self.get_object()
        reason = request.data.get("reason", "")
        cancel_trip(trip, reason)
        return Response(TripReadSerializer(trip).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def generate(self, request):
        try:
            route_id = int(request.data["route_id"])
            schedule_config = request.data["schedule_config"]
            days = int(request.data["days"])
        except (KeyError, TypeError, ValueError):
            raise ValidationError(
                "Champs requis : route_id (int), schedule_config (liste), days (int)."
            )

        # Isolation : le trajet doit appartenir a la compagnie de l'admin.
        if not self.get_company().routes.filter(pk=route_id).exists():
            raise NotFound("Trajet introuvable.")

        trips = generate_trips(route_id, schedule_config, days)
        serializer = TripReadSerializer(trips, many=True)
        return Response(
            {"created": len(trips), "trips": serializer.data},
            status=status.HTTP_201_CREATED,
        )


class PublicTripSearchView(generics.ListAPIView):
    """Recherche publique de voyages.

    Query params : origin_city, dest_city, date, passengers (int),
    max_price, direct (bool). Retourne les voyages programmes ayant assez de
    places, ordonnes par heure de depart.
    """

    serializer_class = TripReadSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        params = self.request.query_params
        # Seuls les voyages a venir et ouverts a la reservation.
        queryset = Trip.objects.filter(
            status__in=[Trip.TripStatus.SCHEDULED, Trip.TripStatus.DELAYED],
            departure_time__gte=timezone.now(),
        ).select_related("route__origin_city", "route__destination_city", "vehicle")

        origin = params.get("origin_city")
        if origin:
            queryset = queryset.filter(route__origin_city_id=origin)

        dest = params.get("dest_city")
        if dest:
            queryset = queryset.filter(route__destination_city_id=dest)

        date = params.get("date")
        if date:
            queryset = queryset.filter(departure_time__date=date)

        passengers = params.get("passengers")
        if passengers:
            try:
                queryset = queryset.filter(available_seats__gte=int(passengers))
            except ValueError:
                raise ValidationError("Le parametre 'passengers' doit etre un entier.")

        max_price = params.get("max_price")
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                raise ValidationError("Le parametre 'max_price' doit etre numerique.")

        # direct=true => trajets sans escale.
        if params.get("direct", "").lower() in {"true", "1"}:
            queryset = queryset.filter(route__stops__isnull=True)

        return queryset.order_by("departure_time")


class PublicTripDetailView(generics.RetrieveAPIView):
    """Detail public d'un voyage + sieges disponibles."""

    serializer_class = TripDetailSerializer
    permission_classes = [AllowAny]
    queryset = Trip.objects.select_related(
        "route__origin_city", "route__destination_city", "vehicle"
    )


class AgentTodayTripsView(generics.ListAPIView):
    """Voyages du jour de la gare/vehicule de l'agent connecte."""

    serializer_class = TripReadSerializer
    permission_classes = [IsAgent]
    pagination_class = None

    def get_queryset(self):
        profile = getattr(self.request.user, "agent_profile", None)
        if profile is None or profile.company_id is None:
            raise NotFound("Aucun profil agent associe a cet utilisateur.")

        queryset = Trip.objects.filter(
            route__company_id=profile.company_id,
            departure_time__date=timezone.localdate(),
        ).select_related("route__origin_city", "route__destination_city", "vehicle")

        # On cible le perimetre de l'agent : son vehicule et/ou sa gare.
        scope = Q()
        if profile.vehicle_id:
            scope |= Q(vehicle_id=profile.vehicle_id)
        if profile.station_id:
            scope |= Q(route__origin_station_id=profile.station_id)
        if scope:
            queryset = queryset.filter(scope)

        return queryset.order_by("departure_time")
