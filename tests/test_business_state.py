import os
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_PATH"] = str(Path(__file__).parent / "test-business.db")

from app.schemas.business_state import BusinessState
from app.services.pii_filter import luhn_valid, redact_free_text, sensitive_kinds
from app.config import settings
from app.database import connection
from app.main import app


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


def _post_state(client, cid, version=1, **changes):
    payload = valid_state(conversation_id=cid, state_version=version, **changes)
    return client.post(f"/internal/conversations/{cid}/state", json=payload, headers={"X-Internal-Key": "test-internal"})


def test_internal_state_auth_idempotence_history_and_unknown_procedure():
    original = settings.internal_api_key
    object.__setattr__(settings, "internal_api_key", "test-internal")
    try:
        with TestClient(app) as client:
            cid = client.post("/api/conversations", json={"channel": "web"}).json()["id"]
            payload = valid_state(conversation_id=cid)
            assert client.post(f"/internal/conversations/{cid}/state", json=payload).status_code == 401
            assert _post_state(client, cid).status_code == 200
            assert _post_state(client, cid).status_code == 200
            assert _post_state(client, cid, version=0).status_code == 422  # schéma: les versions commencent à 1
            unknown = _post_state(client, cid, version=2, procedure={"id": "inconnue", "version": "1", "title": "Non autorisée"})
            assert unknown.status_code == 200
            assert unknown.json()["procedure"]["id"] is None
            assert unknown.json()["procedure_known"] is False
            decreasing = _post_state(client, cid, version=1)
            assert decreasing.status_code == 200
            assert decreasing.json()["state_version"] == 2
            history = client.get(f"/api/conversations/{cid}/state/history").json()
            assert [item["state_version"] for item in history] == [1, 2]
    finally:
        object.__setattr__(settings, "internal_api_key", original)


def test_sensitive_collected_field_is_rejected_and_audited():
    original = settings.internal_api_key
    object.__setattr__(settings, "internal_api_key", "test-internal")
    try:
        with TestClient(app) as client:
            cid = client.post("/api/conversations", json={"channel": "web"}).json()["id"]
            collected = [{"field": "reference", "value": "4111 1111 1111 1111", "source": "caller", "at": "2026-09-03T12:00:00Z"}]
            result = _post_state(client, cid, collected=collected)
            assert result.status_code == 200
            assert result.json()["collected"] == []
            assert result.json()["rejected_fields"] == ["reference"]
            with connection() as db:
                events = [row[0] for row in db.execute("SELECT event FROM business_audit_events WHERE conversation_id=?", (cid,))]
            assert "pii_rejected" in events
    finally:
        object.__setattr__(settings, "internal_api_key", original)


def test_escalation_reuses_one_simulated_ticket():
    original = settings.internal_api_key
    object.__setattr__(settings, "internal_api_key", "test-internal")
    escalation = {"required": True, "type": "conseiller", "reason": "Dossier fictif bloqué", "queued_at": None, "ticket_id": None}
    try:
        with TestClient(app) as client:
            cid = client.post("/api/conversations", json={"channel": "web"}).json()["id"]
            first = _post_state(client, cid, escalation=escalation).json()
            second = _post_state(client, cid, version=2, escalation=escalation).json()
            assert first["escalation"]["ticket_id"] == second["escalation"]["ticket_id"]
            tickets = client.get("/api/queues").json()["conseiller"]
            assert len([ticket for ticket in tickets if ticket["conversation_id"] == cid]) == 1
    finally:
        object.__setattr__(settings, "internal_api_key", original)


def test_internal_endpoint_fails_closed_when_key_is_not_configured():
    original = settings.internal_api_key
    object.__setattr__(settings, "internal_api_key", None)
    try:
        with TestClient(app) as client:
            cid = client.post("/api/conversations", json={"channel": "web"}).json()["id"]
            assert client.post(f"/internal/conversations/{cid}/state", json=valid_state(conversation_id=cid)).status_code == 503
    finally:
        object.__setattr__(settings, "internal_api_key", original)


def test_api_rejects_incoherent_escalation_and_final_state():
    original = settings.internal_api_key
    object.__setattr__(settings, "internal_api_key", "test-internal")
    try:
        with TestClient(app) as client:
            cid = client.post("/api/conversations", json={"channel": "web"}).json()["id"]
            invalid_escalation = valid_state(conversation_id=cid, escalation={"required": True, "type": "conseiller", "reason": None})
            assert client.post(f"/internal/conversations/{cid}/state", json=invalid_escalation, headers={"X-Internal-Key":"test-internal"}).status_code == 422
            invalid_final = valid_state(conversation_id=cid, is_final=True, final_summary=None)
            assert client.post(f"/internal/conversations/{cid}/state", json=invalid_final, headers={"X-Internal-Key":"test-internal"}).status_code == 422
    finally:
        object.__setattr__(settings, "internal_api_key", original)


def test_ivorian_registration_is_kept_by_backend():
    original = settings.internal_api_key
    object.__setattr__(settings, "internal_api_key", "test-internal")
    try:
        with TestClient(app) as client:
            cid = client.post("/api/conversations", json={"channel": "web"}).json()["id"]
            registration = [{"field":"immatriculation","value":"CI-01-234567890123","source":"caller","at":"2026-09-03T12:00:00Z"}]
            result = _post_state(client, cid, collected=registration).json()
            assert result["collected"][0]["value"] == "CI-01-234567890123"
            assert result["rejected_fields"] == []
    finally:
        object.__setattr__(settings, "internal_api_key", original)
