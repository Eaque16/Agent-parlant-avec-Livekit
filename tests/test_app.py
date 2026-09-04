import os
from pathlib import Path

os.environ["DATABASE_PATH"] = str(Path(__file__).parent / "test.db")
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("LIVEKIT_URL", None)
os.environ.pop("LIVEKIT_API_KEY", None)
os.environ.pop("LIVEKIT_API_SECRET", None)

from fastapi.testclient import TestClient
from app.main import app
from app.integrations import IntegrationBlocked, invoke
from app.realtime import create_livekit_token
from agent.prompt import VOICE_AGENT_PROMPT
from agent.worker import _conversation_id
from app.config import settings
import base64
import json


def test_health_and_conversation():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        created = client.post("/api/conversations", json={"channel": "web"})
        assert created.status_code == 201
        cid = created.json()["id"]
        response = client.post(f"/api/conversations/{cid}/messages", json={"text": "Mon portail affiche une erreur"})
        assert response.status_code == 200
        assert response.json()["escalation"] == "it"
        assert response.json()["service"] == "Support IT"
        assert response.json()["procedure"] == "Diagnostic et transfert IT"
        stored = client.get(f"/api/conversations/{cid}").json()
        assert len(stored["messages"]) == 2
        assert stored["status"] == "escalated"


def test_human_escalation():
    with TestClient(app) as client:
        cid = client.post("/api/conversations", json={"channel": "web"}).json()["id"]
        data = client.post(f"/api/conversations/{cid}/messages", json={"text": "Je veux faire une réclamation"}).json()
        assert data["escalation"] == "human"


def test_admin_is_protected_and_phone_webhook_returns_twiml():
    with TestClient(app) as client:
        assert client.get("/api/admin/conversations").status_code == 401
        response = client.post("/telephony/incoming", data={"From": "+2250102030405"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/xml")
        assert "<Gather" in response.text


def test_validated_procedures_are_exposed():
    with TestClient(app) as client:
        procedures = client.get("/api/procedures")
        assert procedures.status_code == 200
        assert {item["service"] for item in procedures.json()} >= {"Adhésion", "Cotisations", "Support IT"}


def test_demo_safety_blocks_payments_and_real_integrations():
    with TestClient(app) as client:
        assert client.get("/api/demo/capabilities").json()["real_payments"] is False
        cid = client.post("/api/conversations", json={"channel": "web"}).json()["id"]
        result = client.post(f"/api/conversations/{cid}/messages", json={"text": "Je veux payer maintenant par carte bancaire"}).json()
        assert "ne traite aucun paiement réel" in result["reply"]
    try:
        invoke("take_payment", {"amount": 1000})
        assert False, "Le paiement aurait dû être bloqué"
    except IntegrationBlocked:
        pass


def test_allowed_future_function_is_only_simulated():
    result = invoke("read_case_status", {"case_ref": "anything"})
    assert result["status"] == "simulated"
    assert result["data"]["case_ref"].startswith("DEMO-")


def test_react_router_entrypoint_is_served():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/conformite").status_code == 200
        assert '<div id="root"></div>' in client.get("/").text


def test_livekit_token_is_ephemeral_and_room_scoped():
    token = create_livekit_token(api_key="demo-key", api_secret="demo-secret", identity="caller-demo",
                                 room_name="asaci-demo-room", ttl_seconds=300)
    payload_part = token.split(".")[1]
    payload = json.loads(base64.urlsafe_b64decode(payload_part + "=" * (-len(payload_part) % 4)))
    assert payload["sub"] == "caller-demo"
    assert payload["video"]["room"] == "asaci-demo-room"
    assert payload["video"]["roomJoin"] is True
    assert payload["exp"] - payload["iat"] == 300


def test_livekit_endpoint_fails_closed_without_cloud_secrets():
    with TestClient(app) as client:
        cid = client.post("/api/conversations", json={"channel": "web"}).json()["id"]
        response = client.post("/api/realtime/token", json={"conversation_id": cid})
        assert response.status_code == 503
        assert "n'est pas configuré" in response.json()["detail"]


def test_voice_agent_prompt_enforces_french_demo_safety():
    assert "exclusivement en français" in VOICE_AGENT_PROMPT
    assert "aucun système ASACI réel" in VOICE_AGENT_PROMPT
    assert "aucune action" in VOICE_AGENT_PROMPT
    assert "paiement" in VOICE_AGENT_PROMPT


def test_agent_room_maps_to_conversation():
    assert _conversation_id("asaci-demo-1234") == "1234"
    assert _conversation_id("untrusted-room") is None


def test_internal_agent_events_require_key_and_are_persisted():
    original = settings.agent_internal_api_key
    object.__setattr__(settings, "agent_internal_api_key", "test-agent-secret")
    try:
        with TestClient(app) as client:
            cid = client.post("/api/conversations", json={"channel": "web"}).json()["id"]
            payload = {"role": "user", "content": "Transcription fictive", "event_type": "transcript"}
            assert client.post(f"/api/internal/conversations/{cid}/agent-events", json=payload).status_code == 401
            stored = client.post(f"/api/internal/conversations/{cid}/agent-events", json=payload,
                                 headers={"X-Agent-Key": "test-agent-secret"})
            assert stored.status_code == 200
            assert client.get(f"/api/conversations/{cid}").json()["messages"][-1]["content"] == "Transcription fictive"
    finally:
        object.__setattr__(settings, "agent_internal_api_key", original)
