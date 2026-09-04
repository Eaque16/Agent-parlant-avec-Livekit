"""Back-office protégé par la clé administrateur."""

from fastapi import APIRouter, Depends

from .. import database as db
from .deps import require_admin

router = APIRouter(prefix="/api/admin", tags=["administration"], dependencies=[Depends(require_admin)])


@router.get("/conversations")
def list_conversations(limit: int = 100):
    return db.list_conversations(min(max(limit, 1), 500))


@router.post("/retention/purge")
def purge_retention():
    return {"deleted": db.purge_expired()}
