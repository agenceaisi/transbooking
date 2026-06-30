from django.conf import settings
from django.db import models
from django.db.models import Q

from utils.models import TimeStampedModel


class BookingStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    PAID = "paid", "Paye"
    CANCELLED = "cancelled", "Annule"
    REFUNDED = "refunded", "Rembourse"


class BoardingMethod(models.TextChoices):
    SCAN = "scan", "Scan QR"
    MANUAL = "manual", "Manuel"


class Booking(TimeStampedModel):
    """Reservation d'un siege sur un voyage.

    Coeur du systeme : peut etre creee par un voyageur (en ligne) ou par un
    agent guichet (eventuellement hors ligne). Le siege est decremente sur le
    voyage via `select_for_update()` (cf. business_rules.md §1).
    """

    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    # Voyageur authentifie a l'origine de la reservation (null pour un walk-in
    # enregistre au guichet sans compte client).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
    )
    # Agent guichet ayant saisi la reservation (null pour une reservation en ligne).
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="agent_bookings",
        null=True,
        blank=True,
    )

    # Identite du passager (peut differer du compte voyageur).
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)

    seat_number = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, blank=True)

    # Genere automatiquement : "BF" + annee + sequence a 6 chiffres (BF2026001234).
    ticket_number = models.CharField(max_length=20, unique=True)
    # PNG base64 encodant le ticket_number (jamais l'id DB).
    qr_code = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
    )
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="cancelled_bookings",
        null=True,
        blank=True,
    )

    # Mode hors ligne (cf. CLAUDE.md « Mode hors ligne »).
    is_offline = models.BooleanField(default=False)
    offline_created_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Reservation"
        verbose_name_plural = "Reservations"
        constraints = [
            # Un siege ne peut etre occupe que par une reservation active a la fois.
            models.UniqueConstraint(
                fields=["trip", "seat_number"],
                condition=~Q(status="cancelled"),
                name="unique_active_seat_per_trip",
            ),
        ]

    def __str__(self) -> str:
        return self.ticket_number

    @property
    def passenger_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class BoardingValidation(TimeStampedModel):
    """Embarquement d'un passager controle a la montee dans le vehicule."""

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="boarding_validation",
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="boarding_validations",
        null=True,
        blank=True,
    )
    method = models.CharField(
        max_length=10,
        choices=BoardingMethod.choices,
        default=BoardingMethod.SCAN,
    )
    boarded_at = models.DateTimeField()

    # Mode hors ligne (validation faite sans connexion puis synchronisee).
    is_offline = models.BooleanField(default=False)
    offline_created_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-boarded_at"]
        verbose_name = "Embarquement"
        verbose_name_plural = "Embarquements"

    def __str__(self) -> str:
        return f"Embarquement {self.booking.ticket_number}"
