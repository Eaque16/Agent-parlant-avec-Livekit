import hmac

from fastapi import APIRouter, Header, HTTPException

from ..config import settings
from ..database import get_conversation
from ..schemas.business_state import BusinessState, BusinessStateOut
from ..services.business_state_service import get_business_state, get_business_state_history, save_business_state
from ..services.queues import list_queues
from .ws import state_connections


router = APIRouter()


@router.post("/internal/conversations/{conversation_id}/state", response_model=BusinessStateOut)
async def write_state(conversation_id: str, payload: BusinessState, x_internal_key: str = Header(default="")):
    if not settings.internal_api_key:
        raise HTTPException(503, "API interne non configurée")
    if not hmac.compare_digest(x_internal_key, settings.internal_api_key):
        raise HTTPException(401, "Authentification interne invalide")
    try:
        state, written = save_business_state(conversation_id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if written:
        await state_connections.broadcast(conversation_id, state.model_dump(mode="json"))
    return state


@router.get("/api/conversations/{conversation_id}/state", response_model=BusinessStateOut)
def read_state(conversation_id: str):
    if not get_conversation(conversation_id):
        raise HTTPException(404, "Conversation introuvable")
    state = get_business_state(conversation_id)
    if not state:
        raise HTTPException(404, "Aucun état métier disponible")
    return state


@router.get("/api/conversations/{conversation_id}/state/history", response_model=list[BusinessStateOut])
def read_state_history(conversation_id: str):
    if not get_conversation(conversation_id):
        raise HTTPException(404, "Conversation introuvable")
    return get_business_state_history(conversation_id)


@router.get("/api/queues")
def queues():
    return list_queues()
