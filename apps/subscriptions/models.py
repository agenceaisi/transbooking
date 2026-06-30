from django.db import models

from utils.models import TimeStampedModel


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    EXPIRED = "expired", "Expire"
    CANCELLED = "cancelled", "Annule"


class SubscriptionPlan(TimeStampedModel):
    """Forfait d'abonnement propose aux compagnies par le super admin.

    Definit le prix et la duree (en jours) ainsi que des quotas indicatifs.
    Un abonnement (`Subscription`) rattache une compagnie a un forfait.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Duree de validite du forfait, utilisee pour le renouvellement automatique.
    duration_days = models.PositiveIntegerField(default=30)
    max_vehicles = models.PositiveIntegerField(null=True, blank=True)
    max_agents = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price"]
        verbose_name = "Forfait"
        verbose_name_plural = "Forfaits"

    def __str__(self) -> str:
        return self.name


class Subscription(TimeStampedModel):
    """Abonnement courant d'une compagnie a un forfait.

    Une compagnie possede au plus un abonnement (`OneToOne`). La tache
    `subscriptions.tasks.check_expiring_subscriptions` previent la compagnie 7
    jours avant `end_date`, puis renouvelle (si `auto_renew`) ou suspend la
    compagnie a l'expiration (cf. PROMPT 12).
    """

    company = models.OneToOneField(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
    )
    auto_renew = models.BooleanField(default=False)
    # Garde-fou d'idempotence : le SMS « expire dans 7 jours » n'est envoye
    # qu'une fois par cycle (remis a False a chaque renouvellement).
    expiry_reminder_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ["end_date"]
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"
        indexes = [
            models.Index(fields=["status", "end_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.company.name} - {self.plan.name}"
