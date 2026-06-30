from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AgentTodayTripsView,
    CompanyTripViewSet,
    PublicTripDetailView,
    PublicTripSearchView,
)


app_name = "trips"

router = DefaultRouter()
router.register("company/trips", CompanyTripViewSet, basename="company-trips")

urlpatterns = [
    path("trips/search/", PublicTripSearchView.as_view(), name="trip-search"),
    path("trips/<int:pk>/", PublicTripDetailView.as_view(), name="trip-detail"),
    path("agent/trips/today/", AgentTodayTripsView.as_view(), name="agent-trips-today"),
    path("", include(router.urls)),
]
