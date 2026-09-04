import sqlite3
from uuid import uuid4

from ..database import utcnow


QUEUE_TYPES = {"conseiller", "support_it", "pool_tpv"}


def get_or_create_ticket(db: sqlite3.Connection, conversation_id: str, escalation_type: str, reason: str) -> dict:
    existing = db.execute(
        "SELECT * FROM escalation_tickets WHERE conversation_id=? AND type=?",
        (conversation_id, escalation_type),
    ).fetchone()
    if existing:
        return dict(existing)
    if escalation_type not in QUEUE_TYPES:
        raise ValueError("File d'escalade inconnue")
    ticket = {
        "ticket_id": f"SIM-{uuid4().hex[:12].upper()}",
        "conversation_id": conversation_id,
        "type": escalation_type,
        "reason": reason,
        "created_at": utcnow(),
        "status": "simule_en_attente",
    }
    db.execute(
        "INSERT INTO escalation_tickets(ticket_id,conversation_id,type,reason,created_at,status) VALUES (:ticket_id,:conversation_id,:type,:reason,:created_at,:status)",
        ticket,
    )
    return ticket


def list_queues() -> dict[str, list[dict]]:
    from ..database import connection
    result = {name: [] for name in sorted(QUEUE_TYPES)}
    with connection() as db:
        for row in db.execute("SELECT * FROM escalation_tickets ORDER BY created_at"):
            result[row["type"]].append(dict(row))
    return result
