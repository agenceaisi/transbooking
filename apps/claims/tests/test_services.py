import pytest
from rest_framework.exceptions import ValidationError

from apps.claims.models import ClaimStatus
from apps.claims.services import close_claim, escalate_claim, respond_to_claim

from .factories import ClaimFactory


@pytest.mark.django_db
def test_respond_rejects_invalid_status():
    claim = ClaimFactory()
    with pytest.raises(ValidationError):
        respond_to_claim(claim, response="ok", status="submitted", responder=None)


@pytest.mark.django_db
def test_escalate_then_close_keeps_response_timestamp():
    claim = ClaimFactory(status=ClaimStatus.SUBMITTED)
    escalate_claim(claim)
    assert claim.status == ClaimStatus.ESCALATED

    close_claim(claim)
    assert claim.status == ClaimStatus.CLOSED
    # Cloture directe sans reponse prealable => horodatage de cloture pose.
    assert claim.responded_at is not None
