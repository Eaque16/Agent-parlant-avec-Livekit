"""Tests du contrat d'état métier : invariants, filtrage des données sensibles, versions et files simulées."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.database import connection
from app.schemas.business_state import BusinessState
from app.services.pii_filter import luhn_valid, redact_free_text, sensitive_kinds


def valid_state(**changes) -> dict:
    value = {
        "conversation_id": str(uuid4()),
        "state_version": 1,
        "language": "fr",
        "service": "adhesion",
        "intent": {"label": "adhesion", "confidence": 0.9, "reformulation": "Vous souhaitez adhérer."},
        "procedure": {"id": "adhesion-qualification", "version": "1", "title": "Adhésion"},
        "step": {"index": 1, "total": 3, "label": "Qualification"},
        "next_question": "S'agit-il d'une nouvelle adhésion ?",
        "collected": [],
        "missing": ["type_demande"],
        "resolution": {"status": "none", "text": None},
        "escalation": {"required": False, "type": "none", "reason": None, "queued_at": None, "ticket_id": None},
        "risk_flags": [],
        "final_summary": None,
        "is_final": False,
    }
    value.update(changes)
    return value


def post_state(client, conversation_id, key, version=1, **changes):
    payload = valid_state(conversation_id=conversation_id, state_version=version, **changes)
    return client.post(
        f"/internal/conversations/{conversation_id}/state",
        json=payload,
        headers={"X-Internal-Key": key},
    )


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


def test_internal_state_auth_idempotence_history_and_unknown_procedure(client, conversation_id, internal_key):
    payload = valid_state(conversation_id=conversation_id)
    assert client.post(f"/internal/conversations/{conversation_id}/state", json=payload).status_code == 401
    assert post_state(client, conversation_id, internal_key).status_code == 200
    assert post_state(client, conversation_id, internal_key).status_code == 200
    # Le schéma impose des versions à partir de 1.
    assert post_state(client, conversation_id, internal_key, version=0).status_code == 422

    unknown = post_state(
        client,
        conversation_id,
        internal_key,
        version=2,
        procedure={"id": "inconnue", "version": "1", "title": "Non autorisée"},
    )
    assert unknown.status_code == 200
    assert unknown.json()["procedure"]["id"] is None
    assert unknown.json()["procedure_known"] is False

    decreasing = post_state(client, conversation_id, internal_key, version=1)
    assert decreasing.status_code == 200
    assert decreasing.json()["state_version"] == 2

    history = client.get(f"/api/conversations/{conversation_id}/state/history").json()
    assert [item["state_version"] for item in history] == [1, 2]


def test_state_of_unknown_conversation_is_rejected(client, internal_key):
    unknown_id = str(uuid4())
    assert post_state(client, unknown_id, internal_key).status_code == 404
    assert client.get(f"/api/conversations/{unknown_id}/state").status_code == 404


def test_sensitive_collected_field_is_rejected_and_audited(client, conversation_id, internal_key):
    collected = [
        {"field": "reference", "value": "4111 1111 1111 1111", "source": "caller", "at": "2026-09-03T12:00:00Z"}
    ]
    result = post_state(client, conversation_id, internal_key, collected=collected)
    assert result.status_code == 200
    assert result.json()["collected"] == []
    assert result.json()["rejected_fields"] == ["reference"]
    with connection() as db:
        rows = db.execute("SELECT event FROM business_audit_events WHERE conversation_id=?", (conversation_id,))
        events = [row[0] for row in rows]
    assert "pii_rejected" in events


def test_escalation_reuses_one_simulated_ticket(client, conversation_id, internal_key):
    escalation = {
        "required": True,
        "type": "conseiller",
        "reason": "Dossier fictif bloqué",
        "queued_at": None,
        "ticket_id": None,
    }
    first = post_state(client, conversation_id, internal_key, escalation=escalation).json()
    second = post_state(client, conversation_id, internal_key, version=2, escalation=escalation).json()
    assert first["escalation"]["ticket_id"] == second["escalation"]["ticket_id"]
    tickets = client.get("/api/queues").json()["conseiller"]
    assert len([ticket for ticket in tickets if ticket["conversation_id"] == conversation_id]) == 1


def test_internal_endpoint_fails_closed_when_key_is_not_configured(client, conversation_id):
    response = client.post(
        f"/internal/conversations/{conversation_id}/state", json=valid_state(conversation_id=conversation_id)
    )
    assert response.status_code == 503


def test_api_rejects_incoherent_escalation_and_final_state(client, conversation_id, internal_key):
    invalid_escalation = post_state(
        client,
        conversation_id,
        internal_key,
        escalation={"required": True, "type": "conseiller", "reason": None},
    )
    assert invalid_escalation.status_code == 422
    invalid_final = post_state(client, conversation_id, internal_key, is_final=True, final_summary=None)
    assert invalid_final.status_code == 422


def test_ivorian_registration_is_kept_by_backend(client, conversation_id, internal_key):
    registration = [
        {"field": "immatriculation", "value": "CI-01-234567890123", "source": "caller", "at": "2026-09-03T12:00:00Z"}
    ]
    result = post_state(client, conversation_id, internal_key, collected=registration).json()
    assert result["collected"][0]["value"] == "CI-01-234567890123"
    assert result["rejected_fields"] == []
