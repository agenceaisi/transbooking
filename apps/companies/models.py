from django.db import models

from utils.models import TimeStampedModel


class Company(TimeStampedModel):
    class CompanyStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REJECTED = "rejected", "Rejected"

    name = models.CharField(max_length=150)
    responsible_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=CompanyStatus.choices,
        default=CompanyStatus.PENDING,
    )
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self) -> str:
        return self.name
