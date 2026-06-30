import re
from collections import Counter

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking, BookingStatus
from apps.trips.models import Trip

from .models import Review

# Mots vides (francais) exclus du nuage de mots.
STOP_WORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "a", "au", "aux",
    "en", "est", "il", "elle", "ils", "elles", "je", "tu", "nous", "vous",
    "pour", "par", "sur", "avec", "sans", "mais", "ou", "que", "qui", "ce",
    "cette", "ces", "son", "sa", "ses", "mon", "ma", "mes", "ne", "pas",
    "plus", "tres", "trop", "dans", "se", "ete", "etait", "y",
}


def can_review(user, trip: Trip) -> bool:
    """Return whether a user may review a trip (cf. business_rules.md §4).

    Args:
        user: The traveller wishing to review.
        trip: The trip being reviewed.

    Returns:
        True if the trip is completed and the user has a paid booking on it.
    """
    return (
        trip.status == Trip.TripStatus.COMPLETED
        and Booking.objects.filter(
            user=user, trip=trip, status=BookingStatus.PAID
        ).exists()
    )


def create_review(validated_data: dict, user) -> Review:
    """Create a review after enforcing the eligibility rules.

    Args:
        validated_data: Cleaned fields containing ``trip``, ``rating`` and
            optionally ``comment``.
        user: The authenticated traveller leaving the review.

    Returns:
        The created review.

    Raises:
        ValidationError: If the trip is not completed, the user has no paid
            booking on it, or the user already reviewed this trip.
    """
    trip = validated_data["trip"]
    if not can_review(user, trip):
        raise ValidationError(
            "Vous ne pouvez noter que les voyages termines pour lesquels vous "
            "avez une reservation payee."
        )
    if Review.objects.filter(user=user, trip=trip).exists():
        raise ValidationError("Vous avez deja depose un avis pour ce voyage.")

    return Review.objects.create(
        company=trip.route.company,
        user=user,
        trip=trip,
        rating=validated_data["rating"],
        comment=validated_data.get("comment", ""),
    )


def respond_to_review(review: Review, response: str) -> Review:
    """Record a company response to a review.

    Args:
        review: The review being answered.
        response: The textual response.

    Returns:
        The updated review.
    """
    review.response = response
    review.responded_at = timezone.now()
    review.save(update_fields=["response", "responded_at", "updated_at"])
    return review


def flag_review(review: Review) -> Review:
    """Flag a review as inappropriate (company admin action).

    Only the super admin can delete a flagged review (cf. business_rules.md §4).

    Args:
        review: The review to flag.

    Returns:
        The updated review.
    """
    review.is_flagged = True
    review.save(update_fields=["is_flagged", "updated_at"])
    return review


def word_cloud(queryset) -> dict:
    """Build a word frequency map from the comments of a set of reviews.

    Args:
        queryset: Reviews to aggregate (already scoped to a company).

    Returns:
        A ``{word: count}`` dict, stop words and short tokens excluded,
        ordered from most to least frequent.
    """
    counter: Counter = Counter()
    for comment in queryset.values_list("comment", flat=True):
        if not comment:
            continue
        for token in re.findall(r"\b[\wàâçéèêëîïôûùüÿñæœ]+\b", comment.lower()):
            if len(token) > 2 and token not in STOP_WORDS:
                counter[token] += 1
    return dict(counter.most_common())
