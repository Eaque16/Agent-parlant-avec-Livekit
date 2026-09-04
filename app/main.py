from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import database as db
from .config import settings
from .services import answer, synthesize, transcribe
from .integrations import AUTHORIZED_FUNCTIONS, FORBIDDEN_FUNCTIONS
from .realtime import create_livekit_token
from .api.business_state import router as business_state_router
from .api.ws import router as websocket_router
from .catalog import PROCEDURES


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    db.purge_expired()
    yield


app = FastAPI(title="Agent vocal ASACI", version="0.1.0", lifespan=lifespan)
app.include_router(business_state_router)
app.include_router(websocket_router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


class ConversationCreate(BaseModel):
    channel: str = Field(default="web", pattern="^(web|phone)$")
    caller_ref: str | None = Field(default=None, max_length=80)


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class RealtimeTokenRequest(BaseModel):
    conversation_id: str


class AgentEventCreate(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=8000)
    event_type: str = Field(pattern="^(transcript|agent_reply|error)$")


def require_admin(x_admin_key: str = Header(default="")) -> None:
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(401, "Clé administrateur invalide")


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/conformite", include_in_schema=False)
def compliance_page():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "mode": "openai" if settings.openai_api_key else "demo", "demo_mode": settings.demo_mode, "integrations_enabled": False}


@app.get("/api/procedures")
def procedures():
    return PROCEDURES


@app.get("/api/demo/capabilities")
def demo_capabilities():
    return {"data_policy": "fictitious_anonymized_only", "real_asaci_connections": False,
            "real_payments": False, "irreversible_actions": False,
            "authorized_future_functions": [vars(item) for item in AUTHORIZED_FUNCTIONS.values()],
            "forbidden_functions": sorted(FORBIDDEN_FUNCTIONS)}


@app.post("/api/realtime/token")
def realtime_token(payload: RealtimeTokenRequest):
    if not db.get_conversation(payload.conversation_id):
        raise HTTPException(404, "Conversation introuvable")
    if not settings.livekit_url or not settings.livekit_api_key or not settings.livekit_api_secret:
        raise HTTPException(503, "LiveKit Cloud n'est pas configuré")
    room_name = f"asaci-demo-{payload.conversation_id}"
    identity = f"caller-{payload.conversation_id[-8:]}"
    token = create_livekit_token(api_key=settings.livekit_api_key, api_secret=settings.livekit_api_secret,
                                 identity=identity, room_name=room_name,
                                 ttl_seconds=settings.livekit_token_ttl_seconds)
    return {"server_url": settings.livekit_url, "token": token, "room_name": room_name,
            "identity": identity, "expires_in": settings.livekit_token_ttl_seconds}


@app.post("/api/internal/conversations/{conversation_id}/agent-events", include_in_schema=False)
def ingest_agent_event(conversation_id: str, payload: AgentEventCreate,
                       x_agent_key: str = Header(default="")):
    if not settings.agent_internal_api_key or not __import__("hmac").compare_digest(x_agent_key, settings.agent_internal_api_key):
        raise HTTPException(401, "Authentification agent invalide")
    if not db.get_conversation(conversation_id):
        raise HTTPException(404, "Conversation introuvable")
    if payload.event_type in {"transcript", "agent_reply"}:
        db.add_message(conversation_id, payload.role, payload.content)
    db.add_audit_event(conversation_id, payload.event_type, {"role": payload.role, "source": "livekit-agent"})
    return {"stored": True}


@app.post("/api/conversations", status_code=201)
def new_conversation(payload: ConversationCreate):
    return db.create_conversation(payload.channel, payload.caller_ref)


@app.get("/api/conversations/{conversation_id}")
def conversation(conversation_id: str):
    result = db.get_conversation(conversation_id)
    if not result:
        raise HTTPException(404, "Conversation introuvable")
    return result


@app.post("/api/conversations/{conversation_id}/messages")
def message(conversation_id: str, payload: MessageCreate):
    current = db.get_conversation(conversation_id)
    if not current:
        raise HTTPException(404, "Conversation introuvable")
    db.add_message(conversation_id, "user", payload.text)
    outcome = answer(current["messages"], payload.text)
    db.add_message(conversation_id, "assistant", outcome["reply"])
    db.update_outcome(conversation_id, outcome["intent"], outcome["escalation"], outcome.get("reason", ""))
    return {"transcript": payload.text, **outcome}


@app.post("/api/conversations/{conversation_id}/audio")
async def audio_message(conversation_id: str, audio: UploadFile = File(...)):
    if not db.get_conversation(conversation_id):
        raise HTTPException(404, "Conversation introuvable")
    try:
        text = transcribe(await audio.read(), audio.filename or "audio.webm", audio.content_type)
        result = message(conversation_id, MessageCreate(text=text))
        voice = synthesize(result["reply"])
        result["audio_base64"] = __import__("base64").b64encode(voice).decode() if voice else None
        return result
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/admin/conversations", dependencies=[Depends(require_admin)])
def admin_conversations(limit: int = 100):
    return db.list_conversations(min(max(limit, 1), 500))


@app.post("/api/admin/retention/purge", dependencies=[Depends(require_admin)])
def retention_purge():
    return {"deleted": db.purge_expired()}


def twiml(body: str) -> Response:
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>', media_type="application/xml")


@app.post("/telephony/incoming")
def incoming_call(From: str = Form(default="anonymous")):
    conv = db.create_conversation("phone", From[-4:] if From else "anonymous")
    action = f"{settings.public_base_url}/telephony/turn/{conv['id']}"
    return twiml(f'<Gather input="speech" language="fr-FR" speechTimeout="auto" action="{escape(action)}"><Say language="fr-FR">Bonjour, vous êtes en ligne avec l’assistante vocale de l’ASACI. Comment puis-je vous aider ?</Say></Gather><Redirect>{escape(action)}</Redirect>')


@app.post("/telephony/turn/{conversation_id}")
def phone_turn(conversation_id: str, SpeechResult: str = Form(default="")):
    if not SpeechResult:
        return twiml('<Say language="fr-FR">Je n’ai pas entendu votre demande. Merci de rappeler ultérieurement.</Say>')
    result = message(conversation_id, MessageCreate(text=SpeechResult))
    spoken = escape(result["reply"])
    if result["escalation"] != "none":
        return twiml(f'<Say language="fr-FR">{spoken}</Say><Say language="fr-FR">Votre demande a été enregistrée pour prise en charge.</Say>')
    action = f"{settings.public_base_url}/telephony/turn/{conversation_id}"
    return twiml(f'<Gather input="speech" language="fr-FR" speechTimeout="auto" action="{escape(action)}"><Say language="fr-FR">{spoken}</Say></Gather>')
