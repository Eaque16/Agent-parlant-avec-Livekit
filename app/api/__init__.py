"""Routeurs HTTP et WebSocket de l'API."""

from . import admin, business_state, conversations, internal, system, telephony, ws

ROUTERS = (
    system.router,
    conversations.router,
    business_state.router,
    internal.router,
    admin.router,
    telephony.router,
    ws.router,
)

__all__ = ["ROUTERS"]
