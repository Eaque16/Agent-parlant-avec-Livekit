import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from livekit.agents.llm import function_tool

from app.services.pii_filter import sensitive_kinds


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class BusinessStateTracker:
    conversation_id: str
    state_version: int = 0
    service: str = "inconnu"
    intent: dict[str, Any] = field(
        default_factory=lambda: {"label": "non_identifiee", "confidence": 0.0, "reformulation": "Besoin à préciser."}
    )
    procedure: dict[str, Any] = field(default_factory=lambda: {"id": None, "version": None, "title": None})
    step: dict[str, Any] = field(default_factory=lambda: {"index": 0, "total": 0, "label": None})
    next_question: str | None = None
    collected: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    resolution: dict[str, Any] = field(default_factory=lambda: {"status": "none", "text": None})
    escalation: dict[str, Any] = field(
        default_factory=lambda: {
            "required": False,
            "type": "none",
            "reason": None,
            "queued_at": None,
            "ticket_id": None,
        }
    )
    risk_flags: list[str] = field(default_factory=list)
    final_summary: str | None = None
    is_final: bool = False
    misunderstanding_count: int = 0

    def snapshot(self, increment: bool = True) -> dict:
        if increment:
            self.state_version += 1
        return {
            "conversation_id": self.conversation_id,
            "state_version": self.state_version,
            "updated_at": _now(),
            "language": "fr",
            "service": self.service,
            "intent": self.intent,
            "procedure": self.procedure,
            "step": self.step,
            "next_question": self.next_question,
            "collected": list(self.collected),
            "missing": list(self.missing),
            "resolution": self.resolution,
            "escalation": self.escalation,
            "risk_flags": list(dict.fromkeys(self.risk_flags)),
            "final_summary": self.final_summary,
            "is_final": self.is_final,
        }


def create_business_tools(tracker: BusinessStateTracker, publisher, procedures: list[dict]):
    procedure_by_id = {item["id"]: item for item in procedures}

    async def publish() -> dict:
        state = tracker.snapshot()
        return await publisher.publish_state(state)

    @function_tool(description="Publie l'état métier complet courant après un tour utile.")
    async def set_business_state(
        service: str, intent_label: str, confidence: float, reformulation: str, next_question: str = ""
    ) -> str:
        tracker.service = service
        tracker.intent = {
            "label": intent_label,
            "confidence": max(0.0, min(1.0, confidence)),
            "reformulation": reformulation,
        }
        tracker.next_question = next_question or None
        result = await publish()
        if result["backend"].get("ok"):
            rejected = result["backend"]["state"].get("rejected_fields", [])
            return "État publié et validé." + (
                f" Champs sensibles écartés ({', '.join(rejected)}) : ne les redemande pas." if rejected else ""
            )
        return "État diffusé dans la room, mais non confirmé par le backend. Continue prudemment sans inventer."

    @function_tool(description="Recherche une procédure autorisée en lecture seule.")
    async def lookup_procedure(service: str, intention: str) -> str:
        matches = [
            p
            for p in procedures
            if p.get("service_code") == service
            and intention.lower() in (p.get("name", "") + " " + p.get("id", "")).lower()
        ]
        if not matches:
            matches = [p for p in procedures if p.get("service_code") == service]
        if not matches:
            return "Aucune procédure autorisée. Dis-le à l'appelant et demande une escalade conseiller."
        selected = matches[0]
        tracker.procedure = {"id": selected["id"], "version": selected.get("version"), "title": selected["name"]}
        tracker.step = {
            "index": 1,
            "total": len(selected.get("steps", [])),
            "label": selected.get("steps", [None])[0] if selected.get("steps") else None,
        }
        return "Procédure autorisée : " + json.dumps(selected, ensure_ascii=False)

    @function_tool(description="Enregistre une information utile et non sensible fournie par l'appelant.")
    async def collect_field(field: str, value: str) -> str:
        if sensitive_kinds(value):
            if "donnee_sensible" not in tracker.risk_flags:
                tracker.risk_flags.append("donnee_sensible")
            await publish()
            return (
                "Information sensible refusée et non conservée. "
                "Ne la redemande pas ; explique qu'elle n'est pas nécessaire."
            )
        tracker.collected = [item for item in tracker.collected if item["field"] != field]
        tracker.collected.append({"field": field, "value": value, "source": "caller", "at": _now()})
        tracker.missing = [name for name in tracker.missing if name != field]
        await publish()
        return f"Information « {field} » prise en compte. Poursuis naturellement."

    @function_tool(description="Propose une résolution fictive conforme à une procédure autorisée.")
    async def propose_resolution(text: str, procedure_id: str) -> str:
        if procedure_id not in procedure_by_id:
            return "Procédure inconnue : n'invente pas de résolution et demande une escalade."
        tracker.resolution = {"status": "proposed", "text": text}
        await publish()
        return "Résolution proposée. Présente-la naturellement, sans répéter le contexte de démonstration."

    @function_tool(description="Crée une escalade strictement simulée vers une file autorisée.")
    async def request_escalation(type: str, reason: str, summary: str) -> str:
        tracker.escalation = {
            "required": True,
            "type": type,
            "reason": reason,
            "queued_at": None,
            "ticket_id": tracker.escalation.get("ticket_id"),
        }
        tracker.final_summary = summary or tracker.final_summary
        result = await publish()
        state = result.get("backend", {}).get("state", {})
        ticket = state.get("escalation", {}).get("ticket_id")
        if ticket:
            tracker.escalation["ticket_id"] = ticket
        suffix = f" sous le ticket {ticket}" if ticket else ""
        return (
            f"Orientation enregistrée{suffix}. "
            "Indique sobrement une seule fois que la demande n'est pas transmise dans cet environnement."
        )

    @function_tool(
        description="Refuse explicitement une action interdite et conserve une trace sans exécuter l'action."
    )
    async def refuse_action(action: str, reason: str) -> str:
        if any(word in action.lower() for word in ("paiement", "payer", "carte", "prélèvement")):
            tracker.risk_flags.append("paiement_demande")
        tracker.resolution = {"status": "refused", "text": f"Action refusée : {reason}"}
        await publish()
        return "Action refusée. Explique clairement le motif et propose une escalade conseiller simulée."

    @function_tool(description="Clôture l'appel avec un résumé final obligatoire.")
    async def finalize_call(summary: str) -> str:
        if not summary.strip():
            return "Le résumé est obligatoire. Rédige un résumé utile avant de clôturer."
        tracker.final_summary = summary.strip()
        tracker.is_final = True
        await publish()
        return "Appel clôturé avec un résumé final."

    return [
        set_business_state,
        lookup_procedure,
        collect_field,
        propose_resolution,
        request_escalation,
        refuse_action,
        finalize_call,
    ]
