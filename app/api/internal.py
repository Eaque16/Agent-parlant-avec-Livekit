"""Canal interne réservé au worker vocal : événements de session et états métier."""

from fastapi import APIRouter, Depends, HTTPException

from .. import database as db
from ..schemas.business_state import BusinessState, BusinessStateOut
from ..schemas.conversations import AgentEventCreate
from ..services.business_state_service import save_business_state
from .deps import load_conversation, require_agent_key, require_internal_key
from .ws import state_connections

router = APIRouter(tags=["interne"], include_in_schema=False)


@router.post("/api/internal/conversations/{conversation_id}/agent-events", dependencies=[Depends(require_agent_key)])
def ingest_agent_event(payload: AgentEventCreate, conversation: dict = Depends(load_conversation)):
    conversation_id = conversation["id"]
    if payload.event_type in {"transcript", "agent_reply"}:
        db.add_message(conversation_id, payload.role, payload.content)
    db.add_audit_event(conversation_id, payload.event_type, {"role": payload.role, "source": "livekit-agent"})
    return {"stored": True}


@router.post(
    "/internal/conversations/{conversation_id}/state",
    response_model=BusinessStateOut,
    dependencies=[Depends(require_internal_key)],
)
async def write_state(conversation_id: str, payload: BusinessState):
    try:
        state, written = save_business_state(conversation_id, payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if written:
        await state_connections.broadcast(conversation_id, state.model_dump(mode="json"))
    return state
