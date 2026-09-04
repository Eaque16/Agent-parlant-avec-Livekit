import json
from copy import deepcopy

from .. import database as database
from ..catalog import PROCEDURES_BY_ID
from ..schemas.business_state import BusinessState, BusinessStateOut
from .pii_filter import redact_free_text, sensitive_kinds
from .queues import get_or_create_ticket


def _audit(db, conversation_id: str, version: int, event: str, details: dict | None = None) -> None:
    db.execute(
        "INSERT INTO business_audit_events(conversation_id,state_version,event,details,created_at) VALUES (?,?,?,?,?)",
        (conversation_id, version, event, json.dumps(details or {}, ensure_ascii=False), database.utcnow()),
    )


def _decode(row) -> dict | None:
    return json.loads(row["state_json"]) if row else None


def save_business_state(conversation_id: str, incoming: BusinessState) -> tuple[BusinessStateOut, bool]:
    payload = incoming.model_dump(mode="json")
    if payload["conversation_id"] != conversation_id:
        raise ValueError("L'identifiant de conversation du corps ne correspond pas à l'URL")

    rejected: list[str] = []
    procedure_known = True
    with database.connection() as db:
        if not db.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone():
            raise LookupError("Conversation introuvable")
        current_row = db.execute("SELECT * FROM business_states WHERE conversation_id=?", (conversation_id,)).fetchone()
        if current_row and payload["state_version"] <= current_row["state_version"]:
            _audit(db, conversation_id, payload["state_version"], "state_ignored", {"current_version": current_row["state_version"]})
            current = _decode(current_row)
            return BusinessStateOut.model_validate(current), False

        clean = deepcopy(payload)
        kept = []
        for field in clean["collected"]:
            kinds = sensitive_kinds(field["value"])
            if kinds:
                rejected.append(field["field"])
                _audit(db, conversation_id, clean["state_version"], "pii_rejected", {"field": field["field"], "kinds": sorted(kinds)})
            else:
                kept.append(field)
        clean["collected"] = kept
        for path, container, key in (
            ("resolution.text", clean["resolution"], "text"),
            ("final_summary", clean, "final_summary"),
            ("escalation.reason", clean["escalation"], "reason"),
        ):
            container[key], kinds = redact_free_text(container.get(key))
            if kinds:
                rejected.append(path)
                _audit(db, conversation_id, clean["state_version"], "pii_redacted", {"field": path, "kinds": sorted(kinds)})

        procedure_id = clean["procedure"].get("id")
        if procedure_id and procedure_id not in PROCEDURES_BY_ID:
            clean["procedure"] = {"id": None, "version": None, "title": None}
            procedure_known = False
            _audit(db, conversation_id, clean["state_version"], "unknown_procedure", {"procedure_id": procedure_id})

        if clean["escalation"]["required"]:
            ticket = get_or_create_ticket(db, conversation_id, clean["escalation"]["type"], clean["escalation"]["reason"])
            clean["escalation"]["ticket_id"] = ticket["ticket_id"]
            clean["escalation"]["queued_at"] = ticket["created_at"]

        clean["rejected_fields"] = sorted(set(rejected))
        clean["procedure_known"] = procedure_known
        canonical = BusinessStateOut.model_validate(clean).model_dump(mode="json")
        encoded = json.dumps(canonical, ensure_ascii=False)
        now = database.utcnow()
        db.execute(
            "INSERT INTO business_states(conversation_id,state_version,state_json,updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET state_version=excluded.state_version,state_json=excluded.state_json,updated_at=excluded.updated_at",
            (conversation_id, clean["state_version"], encoded, now),
        )
        db.execute(
            "INSERT INTO business_state_history(conversation_id,state_version,state_json,created_at) VALUES (?,?,?,?)",
            (conversation_id, clean["state_version"], encoded, now),
        )
        _audit(db, conversation_id, clean["state_version"], "state_saved")
        return BusinessStateOut.model_validate(canonical), True


def get_business_state(conversation_id: str) -> BusinessStateOut | None:
    with database.connection() as db:
        row = db.execute("SELECT state_json FROM business_states WHERE conversation_id=?", (conversation_id,)).fetchone()
        return BusinessStateOut.model_validate(_decode(row)) if row else None


def get_business_state_history(conversation_id: str) -> list[BusinessStateOut]:
    with database.connection() as db:
        rows = db.execute("SELECT state_json FROM business_state_history WHERE conversation_id=? ORDER BY state_version", (conversation_id,)).fetchall()
        return [BusinessStateOut.model_validate(_decode(row)) for row in rows]
