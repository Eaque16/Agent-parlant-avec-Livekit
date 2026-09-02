import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from .config import settings


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript("""
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
        """)


@contextmanager
def connection():
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
        db.execute("INSERT INTO conversations VALUES (?, ?, ?, 'open', NULL, 'none', NULL, ?, ?)",
                   (conversation_id, channel, caller_ref, now, now))
    return get_conversation(conversation_id)


def add_message(conversation_id: str, role: str, content: str) -> None:
    with connection() as db:
        db.execute("INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                   (conversation_id, role, content, utcnow()))
        db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (utcnow(), conversation_id))


def update_outcome(conversation_id: str, intent: str, escalation: str, reason: str) -> None:
    status = "escalated" if escalation != "none" else "open"
    with connection() as db:
        db.execute("UPDATE conversations SET intent=?, escalation=?, escalation_reason=?, status=?, updated_at=? WHERE id=?",
                   (intent, escalation, reason or None, status, utcnow(), conversation_id))
        if escalation != "none":
            db.execute("INSERT INTO audit_events(conversation_id,event_type,payload,created_at) VALUES (?, 'escalation', ?, ?)",
                       (conversation_id, json.dumps({"target": escalation, "reason": reason}), utcnow()))


def add_audit_event(conversation_id: str, event_type: str, payload: dict) -> None:
    with connection() as db:
        db.execute("INSERT INTO audit_events(conversation_id,event_type,payload,created_at) VALUES (?, ?, ?, ?)",
                   (conversation_id, event_type, json.dumps(payload, ensure_ascii=False), utcnow()))


def get_conversation(conversation_id: str) -> dict | None:
    with connection() as db:
        row = db.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["messages"] = [dict(x) for x in db.execute(
            "SELECT role,content,created_at FROM messages WHERE conversation_id=? ORDER BY id", (conversation_id,))]
        return result


def list_conversations(limit: int = 100) -> list[dict]:
    with connection() as db:
        return [dict(x) for x in db.execute("SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?", (limit,))]


def purge_expired() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.retention_days)).isoformat()
    with connection() as db:
        ids = [r[0] for r in db.execute("SELECT id FROM conversations WHERE created_at < ?", (cutoff,))]
        for cid in ids:
            db.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
            db.execute("DELETE FROM audit_events WHERE conversation_id=?", (cid,))
            db.execute("DELETE FROM conversations WHERE id=?", (cid,))
    return len(ids)
