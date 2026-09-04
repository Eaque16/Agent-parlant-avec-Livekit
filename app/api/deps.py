"""Dépendances FastAPI partagées : authentification et chargement d'une conversation."""

import hmac

from fastapi import Header, HTTPException

from .. import database as db
from ..config import settings


def _check_key(provided: str, expected: str | None, *, label: str) -> None:
    if not expected:
        raise HTTPException(503, f"{label} non configurée")
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(401, f"{label} invalide")


def require_admin(x_admin_key: str = Header(default="")) -> None:
    _check_key(x_admin_key, settings.admin_api_key, label="Clé administrateur")


def require_agent_key(x_agent_key: str = Header(default="")) -> None:
    _check_key(x_agent_key, settings.agent_internal_api_key, label="Authentification agent")


def require_internal_key(x_internal_key: str = Header(default="")) -> None:
    _check_key(x_internal_key, settings.internal_api_key, label="API interne")


def load_conversation(conversation_id: str) -> dict:
    conversation = db.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation introuvable")
    return conversation
