from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from utils.permissions import IsAgentGuichet

from .models import Payment
from .serializers import (
    AgentPaymentSerializer,
    PaymentInitiateSerializer,
    PaymentReadSerializer,
    PaymentVerifySerializer,
)
from .services import confirm_payment, generate_receipt_pdf, initiate_payment


def _scope_payments(user):
    """Return the payments visible to ``user`` (multi-tenant isolation).

    Args:
        user: The authenticated user.

    Returns:
        A filtered ``Payment`` queryset.
    """
    queryset = Payment.objects.select_related(
        "booking__trip__route__origin_city",
        "booking__trip__route__destination_city",
        "booking__trip__route__company",
    )
    role = getattr(getattr(user, "role", None), "name", None)

    if role == "super_admin":
        return queryset
    if role == "company_admin":
        company = getattr(user, "administered_company", None)
        company_id = getattr(company, "id", None)
        return queryset.filter(booking__trip__route__company_id=company_id)
    if role in {"agent_guichet", "controleur"}:
        profile = getattr(user, "agent_profile", None)
        company_id = getattr(profile, "company_id", None)
        return queryset.filter(booking__trip__route__company_id=company_id)
    # Voyageur : uniquement les paiements de ses propres reservations.
    return queryset.filter(booking__user=user)


class PaymentViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Paiements accessibles a l'utilisateur courant (filtres par perimetre)."""

    permission_classes = [IsAuthenticated]
    serializer_class = PaymentReadSerializer

    def get_queryset(self):
        return _scope_payments(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = PaymentInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payment = initiate_payment(
            booking=data["booking"],
            method=data["method"],
            phone=data.get("phone", ""),
        )
        return Response(
            PaymentReadSerializer(payment).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        payment = self.get_object()
        serializer = PaymentVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = confirm_payment(
            payment, transaction_ref=serializer.validated_data.get("transaction_ref", "")
        )
        return Response(PaymentReadSerializer(payment).data)

    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        payment = self.get_object()
        pdf = generate_receipt_pdf(payment)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="recu_PAY{payment.pk:06d}.pdf"'
        )
        return response


class AgentPaymentView(GenericAPIView):
    """POST /agent/payments/ — encaissement guichet (especes ou Mobile Money).

    L'agent initie et confirme le paiement en une etape.
    """

    permission_classes = [IsAgentGuichet]
    serializer_class = AgentPaymentSerializer

    def post(self, request, *args, **kwargs):
        profile = getattr(request.user, "agent_profile", None)
        if profile is None or profile.company_id is None:
            raise NotFound("Aucun profil agent associe a cet utilisateur.")

        serializer = AgentPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        booking = data["booking"]
        # Isolation multi-tenant : l'agent n'encaisse que pour sa compagnie.
        if booking.trip.route.company_id != profile.company_id:
            raise NotFound("Reservation introuvable.")

        payment = initiate_payment(
            booking=booking,
            method=data["method"],
            phone=data.get("phone", ""),
            agent=request.user,
        )
        payment = confirm_payment(
            payment, transaction_ref=data.get("transaction_ref", "")
        )
        return Response(
            PaymentReadSerializer(payment).data, status=status.HTTP_201_CREATED
        )
