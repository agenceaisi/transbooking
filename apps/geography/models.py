from django.db import models

from utils.models import TimeStampedModel


class City(TimeStampedModel):
    name = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Ville"
        verbose_name_plural = "Villes"

    def __str__(self) -> str:
        return self.name


class Station(TimeStampedModel):
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="stations",
    )
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="stations")
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    localisation = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Gare"
        verbose_name_plural = "Gares"

    def __str__(self) -> str:
        return self.name
