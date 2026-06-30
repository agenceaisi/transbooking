from datetime import date, timedelta

from django.utils import timezone

from .models import Subscription, SubscriptionStatus


def renew_subscription(subscription: Subscription, today: date | None = None) -> Subscription:
    """Extend a subscription by its plan duration from its current end date.

    Resets the expiry reminder flag so the next cycle can warn again. Kept
    idempotent at the caller level: only auto-renewable, expired subscriptions
    should be passed in.

    Args:
        subscription: The subscription to renew.
        today: Reference date (defaults to the local current date). Used as the
            new start date when the previous period already lapsed.

    Returns:
        The renewed subscription.
    """
    today = today or timezone.localdate()
    duration = timedelta(days=subscription.plan.duration_days)
    # On repart de la borne la plus tardive pour ne pas perdre de jours.
    base = max(subscription.end_date, today)
    subscription.start_date = today
    subscription.end_date = base + duration
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.expiry_reminder_sent = False
    subscription.save(
        update_fields=[
            "start_date",
            "end_date",
            "status",
            "expiry_reminder_sent",
            "updated_at",
        ]
    )
    return subscription


def expire_subscription(subscription: Subscription) -> Subscription:
    """Mark a subscription as expired (no auto-renewal).

    The caller is responsible for suspending the company; this only flips the
    subscription status so a re-run does not reprocess it.

    Args:
        subscription: The subscription to expire.

    Returns:
        The expired subscription.
    """
    subscription.status = SubscriptionStatus.EXPIRED
    subscription.save(update_fields=["status", "updated_at"])
    return subscription
