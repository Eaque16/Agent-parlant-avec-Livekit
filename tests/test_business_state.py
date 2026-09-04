import os
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_PATH"] = str(Path(__file__).parent / "test-business.db")

from app.schemas.business_state import BusinessState
from app.services.pii_filter import luhn_valid, redact_free_text, sensitive_kinds


def valid_state(**changes):
    value = {
        "conversation_id": str(uuid4()), "state_version": 1, "language": "fr",
        "service": "adhesion",
        "intent": {"label": "adhesion", "confidence": .9, "reformulation": "Vous souhaitez adhérer."},
        "procedure": {"id": "adhesion-qualification", "version": "1", "title": "Adhésion"},
        "step": {"index": 1, "total": 3, "label": "Qualification"},
        "next_question": "S'agit-il d'une nouvelle adhésion ?", "collected": [], "missing": ["type_demande"],
        "resolution": {"status": "none", "text": None},
        "escalation": {"required": False, "type": "none", "reason": None, "queued_at": None, "ticket_id": None},
        "risk_flags": [], "final_summary": None, "is_final": False,
    }
    value.update(changes)
    return value


def test_business_state_invariants_are_enforced():
    with pytest.raises(ValidationError):
        BusinessState.model_validate(valid_state(step={"index": 4, "total": 3, "label": None}))
    with pytest.raises(ValidationError):
        BusinessState.model_validate(valid_state(escalation={"required": True, "type": "conseiller", "reason": None}))
    with pytest.raises(ValidationError):
        BusinessState.model_validate(valid_state(is_final=True, final_summary=None))


def test_card_requires_luhn_and_reference_is_not_rejected():
    assert luhn_valid("4111 1111 1111 1111")
    assert "carte_bancaire" in sensitive_kinds("Carte 4111 1111 1111 1111")
    assert sensitive_kinds("Immatriculation CI-01-234567890123") == set()


def test_free_text_is_redacted_without_being_discarded():
    cleaned, kinds = redact_free_text("La carte 4111 1111 1111 1111 a été mentionnée dans la demande")
    assert "carte_bancaire" in kinds
    assert "4111" not in cleaned
    assert "mentionnée dans la demande" in cleaned
