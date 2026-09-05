"""Tests de l'API HTTP : conversations, escalades, sécurité et garde-fous du POC."""

import base64
import json

import pytest

from agent.config import settings as agent_settings
from agent.prompts import SYSTEM_PROMPT
from app.config import settings
from app.integrations import IntegrationBlocked, invoke
from app.realtime import create_livekit_token


def test_health_and_it_escalation(client, conversation_id):
    assert client.get("/health").json()["status"] == "ok"
    response = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"text": "Mon portail affiche une erreur"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["escalation"] == "it"
    assert body["service"] == "Support IT"
    assert body["procedure"] == "Diagnostic et transfert IT"
    stored = client.get(f"/api/conversations/{conversation_id}").json()
    assert len(stored["messages"]) == 2
    assert stored["status"] == "escalated"


def test_conversation_is_created_empty(client):
    created = client.post("/api/conversations", json={"channel": "web"})
    assert created.status_code == 201
    assert created.json()["messages"] == []
    assert created.json()["status"] == "open"


def test_unknown_conversation_returns_404(client):
    assert client.get("/api/conversations/inconnue").status_code == 404
    assert client.post("/api/conversations/inconnue/messages", json={"text": "Bonjour"}).status_code == 404


def test_human_escalation(client, conversation_id):
    data = client.post(f"/api/conversations/{conversation_id}/messages", json={"text": "Je veux faire une réclamation"})
    assert data.json()["escalation"] == "human"


def test_admin_routes_require_key(client):
    assert client.get("/api/admin/conversations").status_code == 401
    allowed = client.get("/api/admin/conversations", headers={"X-Admin-Key": settings.admin_api_key})
    assert allowed.status_code == 200
    assert isinstance(allowed.json(), list)


def test_phone_webhook_drives_a_twiml_dialogue(client):
    response = client.post("/telephony/incoming", data={"From": "+2250102030405"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "<Gather" in response.text
    conversation_id = response.text.split("/telephony/turn/")[1].split('"')[0]

    turn = client.post(f"/telephony/turn/{conversation_id}", data={"SpeechResult": "Je souhaite adhérer"})
    assert "<Gather" in turn.text
    assert "immatriculation" in turn.text

    silent = client.post(f"/telephony/turn/{conversation_id}", data={"SpeechResult": ""})
    assert "pas entendu" in silent.text

    stored = client.get(f"/api/conversations/{conversation_id}").json()
    assert stored["channel"] == "phone"
    assert stored["caller_ref"] == "0405"


def test_validated_procedures_are_exposed(client):
    procedures = client.get("/api/procedures")
    assert procedures.status_code == 200
    assert {item["service"] for item in procedures.json()} >= {"Adhésion", "Cotisations", "Support IT"}


def test_demo_safety_blocks_payments_and_real_integrations(client, conversation_id):
    assert client.get("/api/demo/capabilities").json()["real_payments"] is False
    result = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"text": "Je veux payer maintenant par carte bancaire"},
    ).json()
    assert "ne traite aucun paiement réel" in result["reply"]
    with pytest.raises(IntegrationBlocked):
        invoke("take_payment", {"amount": 1000})


def test_allowed_future_function_is_only_simulated():
    result = invoke("read_case_status", {"case_ref": "anything"})
    assert result["status"] == "simulated"
    assert result["data"]["case_ref"].startswith("DEMO-")


def test_react_entrypoint_is_served(client):
    for path in ("/", "/conformite"):
        response = client.get(path)
        assert response.status_code == 200
        assert '<div id="root"></div>' in response.text


def test_livekit_token_is_ephemeral_and_room_scoped():
    token = create_livekit_token(
        api_key="demo-key",
        api_secret="demo-secret",
        identity="caller-demo",
        room_name="asaci-demo-room",
        ttl_seconds=300,
    )
    payload_part = token.split(".")[1]
    payload = json.loads(base64.urlsafe_b64decode(payload_part + "=" * (-len(payload_part) % 4)))
    assert payload["sub"] == "caller-demo"
    assert payload["video"]["room"] == "asaci-demo-room"
    assert payload["video"]["roomJoin"] is True
    assert payload["exp"] - payload["iat"] == 300


def test_livekit_endpoint_fails_closed_without_cloud_secrets(client, conversation_id):
    response = client.post("/api/realtime/token", json={"conversation_id": conversation_id})
    assert response.status_code == 503
    assert "n'est pas configuré" in response.json()["detail"]


def test_voice_agent_prompt_enforces_french_demo_safety():
    assert "uniquement en français" in SYSTEM_PROMPT
    assert "N'invente aucun dossier" in SYSTEM_PROMPT
    assert "aucun paiement et aucune action irréversible" in SYSTEM_PROMPT
    assert "mot de passe" in SYSTEM_PROMPT


def test_agent_room_maps_to_conversation():
    assert agent_settings.conversation_id("asaci-demo-1234") == "1234"
    assert agent_settings.conversation_id("untrusted-room") is None


def test_internal_agent_events_require_key_and_are_persisted(client, conversation_id, agent_key):
    url = f"/api/internal/conversations/{conversation_id}/agent-events"
    payload = {"role": "user", "content": "Transcription fictive", "event_type": "transcript"}
    assert client.post(url, json=payload).status_code == 401
    assert client.post(url, json=payload, headers={"X-Agent-Key": agent_key}).status_code == 200
    assert (
        client.get(f"/api/conversations/{conversation_id}").json()["messages"][-1]["content"] == "Transcription fictive"
    )


def test_call_lifecycle_is_recorded_in_database(client, conversation_id, agent_key):
    url = f"/api/internal/conversations/{conversation_id}/call-events"
    headers = {"X-Agent-Key": agent_key}
    base = {
        "room_name": f"asaci-demo-{conversation_id}",
        "provider": "google",
        "voice": "Kore",
    }

    started = client.post(url, headers=headers, json={**base, "event_type": "started"})
    assert started.status_code == 200
    assert started.json()["call"]["status"] == "active"

    ended = client.post(
        url,
        headers=headers,
        json={**base, "event_type": "ended", "reason": "room_disconnected"},
    )
    assert ended.status_code == 200
    assert ended.json()["call"]["status"] == "ended"
    assert ended.json()["call"]["duration_seconds"] >= 0

    conversation = client.get(f"/api/conversations/{conversation_id}").json()
    assert conversation["status"] == "closed"
    assert len(conversation["calls"]) == 1
    assert conversation["calls"][0]["voice"] == "Kore"
    assert client.get(f"/api/conversations/{conversation_id}/calls").json() == conversation["calls"]


def test_internal_agent_events_fail_closed_without_configured_key(client, conversation_id):
    url = f"/api/internal/conversations/{conversation_id}/agent-events"
    payload = {"role": "user", "content": "Transcription fictive", "event_type": "transcript"}
    assert client.post(url, json=payload, headers={"X-Agent-Key": "anything"}).status_code == 503
