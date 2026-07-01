from django.db import models

from utils.models import TimeStampedModel


class Trip(TimeStampedModel):
    """Voyage planifie : un vehicule parcourt un trajet a une date donnee."""

    class TripStatus(models.TextChoices):
        SCHEDULED = "scheduled", "Programme"
        IN_PROGRESS = "in_progress", "En cours"
        DELAYED = "delayed", "Retarde"
        CANCELLED = "cancelled", "Annule"
        COMPLETED = "completed", "Termine"

    route = models.ForeignKey(
        "routes.Route",
        on_delete=models.PROTECT,
        related_name="trips",
    )
    vehicle = models.ForeignKey(
        "vehicles.Vehicle",
        on_delete=models.PROTECT,
        related_name="trips",
    )
    driver_name = models.CharField(max_length=150, blank=True)
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField(null=True, blank=True)
    # Retard cumule en minutes (0 = a l'heure). Renseigne quand status=delayed.
    delay_minutes = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # Decremente uniquement via select_for_update() (cf. business_rules.md §1).
    available_seats = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=TripStatus.choices,
        default=TripStatus.SCHEDULED,
    )
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["departure_time"]
        verbose_name = "Voyage"
        verbose_name_plural = "Voyages"

    def __str__(self) -> str:
        return f"{self.route} - {self.departure_time:%Y-%m-%d %H:%M}"
