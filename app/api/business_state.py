"""Lecture de l'état métier d'une conversation et des files d'escalade simulées."""

from fastapi import APIRouter, Depends, HTTPException

from ..schemas.business_state import BusinessStateOut
from ..services.business_state_service import get_business_state, get_business_state_history
from ..services.queues import list_queues
from .deps import load_conversation

router = APIRouter(prefix="/api", tags=["état métier"])


@router.get("/conversations/{conversation_id}/state", response_model=BusinessStateOut)
def read_state(conversation: dict = Depends(load_conversation)):
    state = get_business_state(conversation["id"])
    if not state:
        raise HTTPException(404, "Aucun état métier disponible")
    return state


@router.get("/conversations/{conversation_id}/state/history", response_model=list[BusinessStateOut])
def read_state_history(conversation: dict = Depends(load_conversation)):
    return get_business_state_history(conversation["id"])


@router.get("/queues")
def queues():
    return list_queues()
