from django.conf import settings
from django.db import models

from utils.models import TimeStampedModel


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Especes"
    ORANGE_MONEY = "orange_money", "Orange Money"
    MOOV_MONEY = "moov_money", "Moov Money"
    CORIS_MONEY = "coris_money", "Coris Money"
    TELECEL_MONEY = "telecel_money", "Telecel Money"
    CARD = "card", "Carte bancaire"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    PAID = "paid", "Paye"
    FAILED = "failed", "Echoue"
    REFUNDED = "refunded", "Rembourse"


class Payment(TimeStampedModel):
    """Paiement d'une reservation (et, a terme, d'un colis).

    Mode actuel : Mobile Money manuel. L'agent demande la `transaction_ref` au
    client et la saisit (cf. business_rules.md §2). Le systeme ne verifie pas en
    temps reel. La confirmation passe la reservation a `paid`.
    """

    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
    )
    # Paiement de colis : exclusif avec `booking` (cf. mcd.md §7).
    parcel = models.ForeignKey(
        "parcels.Parcel",
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    # Reference de transaction Mobile Money saisie par l'agent. Donnee sensible :
    # masquee dans les logs (cf. security.md §« Donnees sensibles »).
    transaction_ref = models.CharField(max_length=100, blank=True)
    # Numero du payeur (Mobile Money) — facultatif pour les especes.
    phone = models.CharField(max_length=30, blank=True)

    # Commission plateforme figee au moment de la confirmation (cf. business_rules.md §2).
    commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # Renseigne apres confirmation du paiement.
    receipt_url = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Agent guichet ayant encaisse (null pour un paiement initie par le voyageur).
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="collected_payments",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"

    def __str__(self) -> str:
        return f"Paiement {self.pk} - {self.amount} FCFA ({self.status})"
