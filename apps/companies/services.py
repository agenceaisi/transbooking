from django.core.exceptions import ValidationError

from utils.sms import send_sms

from .models import Company, CompanyStatus


def approve_company(company: Company) -> Company:
    """Approve a pending company registration request.

    Sets the company status to active and sends a welcome SMS to the
    legal representative.

    Args:
        company: The pending company to approve.

    Returns:
        The approved company.

    Raises:
        ValidationError: If the company is not in the pending state.
    """
    if company.status != CompanyStatus.PENDING:
        raise ValidationError("Seules les demandes en attente peuvent etre approuvees.")

    company.status = CompanyStatus.ACTIVE
    company.rejection_reason = ""
    company.save(update_fields=["status", "rejection_reason", "updated_at"])

    if company.responsible_phone:
        send_sms(
            company.responsible_phone,
            f"Bienvenue sur TransBooking BF ! La compagnie {company.name} est activee.",
        )
    return company


def reject_company(company: Company, reason: str) -> Company:
    """Reject a pending company registration request.

    Args:
        company: The pending company to reject.
        reason: Human-readable rejection reason (stored and sent by SMS).

    Returns:
        The rejected company.

    Raises:
        ValidationError: If the company is not pending or the reason is empty.
    """
    if company.status != CompanyStatus.PENDING:
        raise ValidationError("Seules les demandes en attente peuvent etre rejetees.")
    if not reason or not reason.strip():
        raise ValidationError({"reason": "Le motif de rejet est obligatoire."})

    company.status = CompanyStatus.REJECTED
    company.rejection_reason = reason.strip()
    company.save(update_fields=["status", "rejection_reason", "updated_at"])

    if company.responsible_phone:
        send_sms(
            company.responsible_phone,
            f"Votre demande TransBooking BF pour {company.name} a ete rejetee : {reason.strip()}",
        )
    return company


def activate_company(company: Company) -> Company:
    """Reactivate a suspended (or pending) company.

    Args:
        company: The company to activate.

    Returns:
        The activated company.

    Raises:
        ValidationError: If the company is already active.
    """
    if company.status == CompanyStatus.ACTIVE:
        raise ValidationError("La compagnie est deja active.")

    company.status = CompanyStatus.ACTIVE
    company.suspension_reason = ""
    company.save(update_fields=["status", "suspension_reason", "updated_at"])

    if company.responsible_phone:
        send_sms(
            company.responsible_phone,
            f"La compagnie {company.name} a ete reactivee sur TransBooking BF.",
        )
    return company


def suspend_company(company: Company, reason: str) -> Company:
    """Suspend an active company and notify its representative.

    Args:
        company: The company to suspend.
        reason: Human-readable suspension reason (stored and sent by SMS).

    Returns:
        The suspended company.

    Raises:
        ValidationError: If the reason is empty.
    """
    if not reason or not reason.strip():
        raise ValidationError({"reason": "Le motif de suspension est obligatoire."})

    company.status = CompanyStatus.SUSPENDED
    company.suspension_reason = reason.strip()
    company.save(update_fields=["status", "suspension_reason", "updated_at"])

    if company.responsible_phone:
        send_sms(
            company.responsible_phone,
            f"La compagnie {company.name} a ete suspendue : {reason.strip()}",
        )
    return company
