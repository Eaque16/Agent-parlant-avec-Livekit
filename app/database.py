"""Persistance SQLite du POC : conversations, messages, audit et rétention."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from .config import settings
from .models.business_state import BUSINESS_STATE_TABLES

CORE_TABLES = """
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, channel TEXT NOT NULL, caller_ref TEXT,
  status TEXT NOT NULL, intent TEXT, escalation TEXT NOT NULL DEFAULT 'none',
  escalation_reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
  role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
  event_type TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS call_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL,
  room_name TEXT NOT NULL,
  provider TEXT NOT NULL,
  voice TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  started_at TEXT NOT NULL,
  ended_at TEXT,
  duration_seconds INTEGER,
  end_reason TEXT,
  FOREIGN KEY(conversation_id) REFERENCES conversations(id),
  UNIQUE(conversation_id, room_name)
);
CREATE INDEX IF NOT EXISTS idx_call_sessions_conversation
  ON call_sessions(conversation_id, started_at);
"""

# Tables rattachées à une conversation, dans l'ordre de suppression.
CONVERSATION_CHILD_TABLES = (
    "business_state_history",
    "business_states",
    "business_audit_events",
    "escalation_tickets",
    "messages",
    "audit_events",
    "call_sessions",
)


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def init_db() -> None:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript(CORE_TABLES)
        db.executescript(BUSINESS_STATE_TABLES)


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(settings.database_path)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()


def create_conversation(channel: str, caller_ref: str | None = None) -> dict:
    conversation_id, now = str(uuid4()), utcnow()
    with connection() as db:
        db.execute(
            "INSERT INTO conversations VALUES (?, ?, ?, 'open', NULL, 'none', NULL, ?, ?)",
            (conversation_id, channel, caller_ref, now, now),
        )
    return get_conversation(conversation_id)


def add_message(conversation_id: str, role: str, content: str) -> None:
    now = utcnow()
    with connection() as db:
        db.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, now),
        )
        db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))


def update_outcome(conversation_id: str, intent: str, escalation: str, reason: str) -> None:
    status = "escalated" if escalation != "none" else "open"
    now = utcnow()
    with connection() as db:
        db.execute(
            "UPDATE conversations SET intent=?, escalation=?, escalation_reason=?, status=?, updated_at=? WHERE id=?",
            (intent, escalation, reason or None, status, now, conversation_id),
        )
        if escalation != "none":
            db.execute(
                "INSERT INTO audit_events(conversation_id, event_type, payload, created_at) "
                "VALUES (?, 'escalation', ?, ?)",
                (conversation_id, json.dumps({"target": escalation, "reason": reason}), now),
            )


def add_audit_event(conversation_id: str, event_type: str, payload: dict) -> None:
    with connection() as db:
        db.execute(
            "INSERT INTO audit_events(conversation_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, event_type, json.dumps(payload, ensure_ascii=False), utcnow()),
        )


def start_call(conversation_id: str, room_name: str, provider: str, voice: str) -> dict:
    """Crée une session d'appel, sans doublon si le worker se reconnecte à la room."""
    now = utcnow()
    with connection() as db:
        db.execute(
            """INSERT INTO call_sessions
               (conversation_id, room_name, provider, voice, status, started_at)
               VALUES (?, ?, ?, ?, 'active', ?)
               ON CONFLICT(conversation_id, room_name) DO UPDATE SET
                 provider=excluded.provider, voice=excluded.voice, status='active',
                 ended_at=NULL, duration_seconds=NULL, end_reason=NULL""",
            (conversation_id, room_name, provider, voice, now),
        )
        db.execute(
            "UPDATE conversations SET status='active', updated_at=? WHERE id=?",
            (now, conversation_id),
        )
        row = db.execute(
            "SELECT * FROM call_sessions WHERE conversation_id=? AND room_name=?",
            (conversation_id, room_name),
        ).fetchone()
        return dict(row)


def end_call(conversation_id: str, room_name: str, reason: str | None = None) -> dict | None:
    """Clôture une session active et calcule sa durée à partir des dates persistées."""
    now = utcnow()
    with connection() as db:
        row = db.execute(
            "SELECT * FROM call_sessions WHERE conversation_id=? AND room_name=?",
            (conversation_id, room_name),
        ).fetchone()
        if not row:
            return None
        if row["status"] == "ended":
            return dict(row)
        started_at = datetime.fromisoformat(row["started_at"])
        duration = max(0, int((datetime.fromisoformat(now) - started_at).total_seconds()))
        db.execute(
            """UPDATE call_sessions SET status='ended', ended_at=?, duration_seconds=?, end_reason=?
               WHERE conversation_id=? AND room_name=?""",
            (now, duration, reason, conversation_id, room_name),
        )
        db.execute(
            "UPDATE conversations SET status='closed', updated_at=? WHERE id=?",
            (now, conversation_id),
        )
        result = db.execute(
            "SELECT * FROM call_sessions WHERE conversation_id=? AND room_name=?",
            (conversation_id, room_name),
        ).fetchone()
        return dict(result)


def list_call_sessions(conversation_id: str) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            "SELECT * FROM call_sessions WHERE conversation_id=? ORDER BY started_at, id",
            (conversation_id,),
        )
        return [dict(row) for row in rows]


def get_conversation(conversation_id: str) -> dict | None:
    with connection() as db:
        row = db.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        messages = db.execute(
            "SELECT role, content, created_at FROM messages WHERE conversation_id=? ORDER BY id",
            (conversation_id,),
        )
        result["messages"] = [dict(message) for message in messages]
        result["calls"] = list_call_sessions(conversation_id)
        return result


def list_conversations(limit: int = 100) -> list[dict]:
    with connection() as db:
        rows = db.execute("SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in rows]


def purge_expired() -> int:
    cutoff = (datetime.now(UTC) - timedelta(days=settings.retention_days)).isoformat()
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM conversations WHERE created_at < ?", (cutoff,))]
        for conversation_id in ids:
            for table in CONVERSATION_CHILD_TABLES:
                db.execute(f"DELETE FROM {table} WHERE conversation_id=?", (conversation_id,))
            db.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
    return len(ids)
