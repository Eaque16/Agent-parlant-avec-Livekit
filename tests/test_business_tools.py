"""Tests des outils métier du worker vocal et de leur intégration avec le service d'état."""

import asyncio
import inspect
from uuid import uuid4

from agent.prompts.asaci_agent_fr import build_instructions
from agent.tools.business_tools import BusinessStateTracker, create_business_tools
from app.schemas.business_state import BusinessState
from app.services.business_state_service import save_business_state

PROCEDURES = [
    {
        "id": "adhesion-qualification",
        "version": "1.0",
        "service_code": "adhesion",
        "name": "Qualification adhésion",
        "steps": ["Qualifier", "Orienter"],
    }
]


class FakePublisher:
    """Accepte tout état sans backend : utile pour tester la logique des outils seule."""

    def __init__(self) -> None:
        self.states: list[dict] = []

    async def publish_state(self, state: dict) -> dict:
        self.states.append(state)
        return {"livekit_ok": True, "backend": {"ok": True, "state": {**state, "rejected_fields": []}}}


class ServicePublisher:
    """Passe par le vrai service d'état, donc par le schéma, le filtrage et la base."""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self.last: dict | None = None

    async def publish_state(self, state: dict) -> dict:
        canonical, _ = save_business_state(self.conversation_id, BusinessState.model_validate(state))
        self.last = canonical.model_dump(mode="json")
        return {"livekit_ok": True, "backend": {"ok": True, "state": self.last}}


def tools_by_name(tracker, publisher):
    return {tool.info.name: tool for tool in create_business_tools(tracker, publisher, PROCEDURES)}


def test_tools_are_closures_without_self_and_publish_complete_states():
    tracker, publisher = BusinessStateTracker(str(uuid4())), FakePublisher()
    tools = tools_by_name(tracker, publisher)
    assert "self" not in inspect.signature(tools["collect_field"]).parameters
    asyncio.run(
        tools["set_business_state"](
            "adhesion", "nouvelle_adhesion", 0.9, "Vous souhaitez adhérer.", "Est-ce une première adhésion ?"
        )
    )
    assert publisher.states[-1]["conversation_id"] == tracker.conversation_id
    assert publisher.states[-1]["intent"]["reformulation"]
    assert publisher.states[-1]["state_version"] == 1


def test_sensitive_value_is_never_collected():
    tracker, publisher = BusinessStateTracker(str(uuid4())), FakePublisher()
    tools = tools_by_name(tracker, publisher)
    asyncio.run(tools["collect_field"]("carte", "4111 1111 1111 1111"))
    assert publisher.states[-1]["collected"] == []
    assert "donnee_sensible" in publisher.states[-1]["risk_flags"]


def test_payment_is_refused_and_finalization_has_summary():
    tracker, publisher = BusinessStateTracker(str(uuid4())), FakePublisher()
    tools = tools_by_name(tracker, publisher)
    asyncio.run(
        tools["refuse_action"]("payer une cotisation", "Les paiements sont interdits dans cette démonstration.")
    )
    assert "paiement_demande" in publisher.states[-1]["risk_flags"]
    asyncio.run(
        tools["request_escalation"]("conseiller", "Paiement demandé", "Paiement refusé et orientation proposée.")
    )
    assert asyncio.run(tools["finalize_call"]("   ")).startswith("Le résumé est obligatoire")
    asyncio.run(tools["finalize_call"]("L'appelant a demandé un paiement, refusé puis orienté."))
    assert publisher.states[-1]["is_final"] is True
    assert publisher.states[-1]["final_summary"]


def test_prompt_contains_catalogue_from_backend():
    instructions = build_instructions(PROCEDURES)
    assert "adhesion-qualification" in instructions
    assert "une question à la fois" in instructions
    assert "assistante virtuelle" in instructions
    assert "ne répète pas" in instructions


def test_complete_adhesion_call_crosses_tools_schema_service_and_database(client, conversation_id):
    tracker, publisher = BusinessStateTracker(conversation_id), ServicePublisher(conversation_id)
    tools = tools_by_name(tracker, publisher)
    asyncio.run(tools["lookup_procedure"]("adhesion", "adhesion"))
    asyncio.run(
        tools["set_business_state"](
            "adhesion",
            "nouvelle_adhesion",
            0.95,
            "Vous souhaitez effectuer une nouvelle adhésion.",
            "S’agit-il de votre première adhésion ?",
        )
    )
    asyncio.run(tools["collect_field"]("type_demande", "nouvelle adhésion"))
    asyncio.run(tools["propose_resolution"]("Orientation fictive vers le guichet adhésion.", "adhesion-qualification"))
    asyncio.run(tools["finalize_call"]("Nouvelle adhésion qualifiée et orientation fictive proposée."))
    assert publisher.last is not None
    assert publisher.last["is_final"] is True
    assert publisher.last["procedure"]["id"] == "adhesion-qualification"
    assert publisher.last["resolution"]["status"] == "proposed"
    assert client.get(f"/api/conversations/{conversation_id}/state").json()["is_final"] is True
