from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from utils.permissions import IsCompanyAdmin, IsVoyageur

from .models import Review
from .serializers import (
    ReviewCreateSerializer,
    ReviewReadSerializer,
    ReviewRespondSerializer,
)
from .services import create_review, flag_review, respond_to_review, word_cloud


def _admin_company(user):
    """Return the company administered by a company admin or raise 404.

    Args:
        user: The authenticated company admin user.

    Returns:
        The administered company.
    """
    company = getattr(user, "administered_company", None)
    if company is None:
        raise NotFound("Aucune compagnie associee a cet utilisateur.")
    return company


# --------------------------------------------------------------------------- #
# Public + voyageur
# --------------------------------------------------------------------------- #


class ReviewViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Avis publics d'une compagnie (lecture) et depot d'un avis (voyageur)."""

    def get_permissions(self):
        if self.action == "create":
            return [IsVoyageur()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.action == "create":
            return ReviewCreateSerializer
        return ReviewReadSerializer

    def get_queryset(self):
        # Liste publique : avis non signales, filtrables par ?company_id=.
        queryset = Review.objects.filter(is_flagged=False).select_related(
            "company", "user"
        )
        company_id = self.request.query_params.get("company_id")
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = create_review(serializer.validated_data, user=request.user)
        return Response(
            ReviewReadSerializer(review).data, status=status.HTTP_201_CREATED
        )


# --------------------------------------------------------------------------- #
# Admin compagnie
# --------------------------------------------------------------------------- #


class CompanyReviewViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Tous les avis de la compagnie de l'admin courant (signales inclus)."""

    permission_classes = [IsCompanyAdmin]
    serializer_class = ReviewReadSerializer

    def get_queryset(self):
        return Review.objects.filter(
            company=_admin_company(self.request.user)
        ).select_related("company", "user")

    @action(detail=True, methods=["post", "patch"])
    def respond(self, request, pk=None):
        """POST/PATCH /company/reviews/{id}/respond/ — repondre a un avis."""
        review = self.get_object()
        serializer = ReviewRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        respond_to_review(review, serializer.validated_data["response"])
        return Response(ReviewReadSerializer(review).data)

    @action(detail=True, methods=["post"])
    def flag(self, request, pk=None):
        """POST /company/reviews/{id}/flag/ — signaler un avis au super admin."""
        review = self.get_object()
        flag_review(review)
        return Response(ReviewReadSerializer(review).data)

    # NB : pas de DestroyModelMixin — l'admin ne peut pas supprimer un avis
    # (cf. business_rules.md §4) ; DELETE renvoie donc 405. Seul le super admin
    # le peut, via l'administration.

    @action(detail=False, methods=["get"], url_path="word-cloud")
    def word_cloud(self, request):
        """GET /company/reviews/word-cloud/ — frequence des mots des avis."""
        return Response(word_cloud(self.get_queryset()))
