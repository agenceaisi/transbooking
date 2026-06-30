from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AgentPaymentView, PaymentViewSet


app_name = "payments"

router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payments")

urlpatterns = [
    path("agent/payments/", AgentPaymentView.as_view(), name="agent-payments"),
    path("", include(router.urls)),
]
