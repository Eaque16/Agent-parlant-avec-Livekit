"""Conversations texte et audio du canal web, et jeton LiveKit éphémère."""

import base64

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from .. import database as db
from ..config import settings
from ..realtime import create_livekit_token
from ..schemas.conversations import ConversationCreate, MessageCreate, RealtimeTokenRequest
from ..services import handle_user_message, synthesize, transcribe
from .deps import load_conversation

router = APIRouter(prefix="/api", tags=["conversations"])


@router.post("/conversations", status_code=201)
def create_conversation(payload: ConversationCreate):
    return db.create_conversation(payload.channel, payload.caller_ref)


@router.get("/conversations/{conversation_id}")
def read_conversation(conversation: dict = Depends(load_conversation)):
    return conversation


@router.post("/conversations/{conversation_id}/messages")
def post_message(payload: MessageCreate, conversation: dict = Depends(load_conversation)):
    return handle_user_message(conversation, payload.text)


@router.post("/conversations/{conversation_id}/audio")
async def post_audio(audio: UploadFile = File(...), conversation: dict = Depends(load_conversation)):
    try:
        text = transcribe(await audio.read(), audio.filename or "audio.webm", audio.content_type).strip()
        if not text:
            raise HTTPException(422, "Aucune parole détectée dans l'enregistrement")
        result = handle_user_message(conversation, text)
        voice = synthesize(result["reply"])
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    result["audio_base64"] = base64.b64encode(voice).decode() if voice else None
    return result


@router.post("/realtime/token")
def realtime_token(payload: RealtimeTokenRequest):
    load_conversation(payload.conversation_id)
    if not (settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret):
        raise HTTPException(503, "LiveKit Cloud n'est pas configuré")
    room_name = f"{settings.livekit_room_prefix}{payload.conversation_id}"
    identity = f"caller-{payload.conversation_id[-8:]}"
    token = create_livekit_token(
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
        identity=identity,
        room_name=room_name,
        ttl_seconds=settings.livekit_token_ttl_seconds,
    )
    return {
        "server_url": settings.livekit_url,
        "token": token,
        "room_name": room_name,
        "identity": identity,
        "expires_in": settings.livekit_token_ttl_seconds,
    }
