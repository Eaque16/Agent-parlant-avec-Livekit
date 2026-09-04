"""Parcours téléphonique compatible TwiML (reconnaissance vocale du fournisseur)."""

from html import escape

from fastapi import APIRouter, Depends, Form
from fastapi.responses import Response

from .. import database as db
from ..config import settings
from ..services import handle_user_message
from .deps import load_conversation

router = APIRouter(prefix="/telephony", tags=["téléphonie"])

GREETING = "Bonjour, vous êtes en ligne avec l’assistante vocale de l’ASACI. Comment puis-je vous aider ?"
NOT_HEARD = "Je n’ai pas entendu votre demande. Merci de rappeler ultérieurement."
HANDOVER = "Votre demande a été enregistrée pour prise en charge."


def twiml(body: str) -> Response:
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>', media_type="application/xml")


def say(text: str) -> str:
    return f'<Say language="fr-FR">{escape(text)}</Say>'


def turn_action(conversation_id: str) -> str:
    return escape(f"{settings.public_base_url}/telephony/turn/{conversation_id}")


def gather(conversation_id: str, text: str) -> str:
    action = turn_action(conversation_id)
    return f'<Gather input="speech" language="fr-FR" speechTimeout="auto" action="{action}">{say(text)}</Gather>'


@router.post("/incoming")
def incoming_call(From: str = Form(default="anonymous")):
    conversation = db.create_conversation("phone", From[-4:] if From else "anonymous")
    return twiml(gather(conversation["id"], GREETING) + f"<Redirect>{turn_action(conversation['id'])}</Redirect>")


@router.post("/turn/{conversation_id}")
def phone_turn(SpeechResult: str = Form(default=""), conversation: dict = Depends(load_conversation)):
    text = SpeechResult.strip()
    if not text:
        return twiml(say(NOT_HEARD))
    result = handle_user_message(conversation, text)
    if result["escalation"] != "none":
        return twiml(say(result["reply"]) + say(HANDOVER))
    return twiml(gather(conversation["id"], result["reply"]))
