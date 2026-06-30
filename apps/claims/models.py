from django.conf import settings
from django.db import models

from utils.models import TimeStampedModel


class ClaimType(models.TextChoices):
    RETARD = "retard", "Retard"
    PERTE_BAGAGE = "perte_bagage", "Perte de bagage"
    BAGAGE_ENDOMMAGE = "bagage_endommage", "Bagage endommage"
    COMPORTEMENT = "comportement", "Comportement"
    SURCHARGE = "surcharge", "Surcharge"
    REMBOURSEMENT = "remboursement", "Remboursement"
    AUTRE = "autre", "Autre"


class ClaimStatus(models.TextChoices):
    SUBMITTED = "submitted", "Soumise"
    IN_PROGRESS = "in_progress", "En traitement"
    RESOLVED = "resolved", "Resolue"
    CLOSED = "closed", "Cloturee"
    ESCALATED = "escalated", "Escaladee"


# Statuts consideres comme « non traites » (pour le tri et les statistiques).
UNRESOLVED_STATUSES = (
    ClaimStatus.SUBMITTED,
    ClaimStatus.IN_PROGRESS,
    ClaimStatus.ESCALATED,
)


class Claim(TimeStampedModel):
    """Reclamation deposee par un voyageur a l'encontre d'une compagnie.

    Le flag `is_overdue` (reponse non fournie sous 48h, cf. business_rules.md §5)
    est annote a la requete dans `services.annotated_claims()`, jamais stocke.
    """

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="claims",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="claims",
    )
    # Reservation concernee : facultative (la reclamation peut etre generale).
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        related_name="claims",
        null=True,
        blank=True,
    )

    claim_type = models.CharField(max_length=20, choices=ClaimType.choices)
    subject = models.CharField(max_length=200)
    description = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=ClaimStatus.choices,
        default=ClaimStatus.SUBMITTED,
    )
    response = models.TextField(blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="claim_responses",
        null=True,
        blank=True,
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Reclamation"
        verbose_name_plural = "Reclamations"

    def __str__(self) -> str:
        return f"{self.get_claim_type_display()} - {self.subject}"
