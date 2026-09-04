"""Traitement d'un tour de conversation : persistance, réponse IA et issue métier."""

from .. import database as db
from .ai import answer


def handle_user_message(conversation: dict, text: str) -> dict:
    conversation_id = conversation["id"]
    db.add_message(conversation_id, "user", text)
    outcome = answer(conversation["messages"], text)
    db.add_message(conversation_id, "assistant", outcome["reply"])
    db.update_outcome(conversation_id, outcome["intent"], outcome["escalation"], outcome.get("reason", ""))
    return {"transcript": text, **outcome}
