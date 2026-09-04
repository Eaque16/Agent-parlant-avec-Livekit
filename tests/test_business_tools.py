import asyncio
import inspect
from uuid import uuid4

from agent.prompts.asaci_agent_fr import build_instructions
from agent.tools.business_tools import BusinessStateTracker, create_business_tools


class FakePublisher:
    def __init__(self):
        self.states = []

    async def publish_state(self, state):
        self.states.append(state)
        return {"livekit_ok": True, "backend": {"ok": True, "state": {**state, "rejected_fields": []}}}


PROCEDURES = [{"id": "adhesion-qualification", "version": "1.0", "service_code": "adhesion", "name": "Qualification adhésion", "steps": ["Qualifier", "Orienter"]}]


def tools_by_name(tracker, publisher):
    return {tool.info.name: tool for tool in create_business_tools(tracker, publisher, PROCEDURES)}


def test_tools_are_closures_without_self_and_publish_complete_states():
    tracker, publisher = BusinessStateTracker(str(uuid4())), FakePublisher()
    tools = tools_by_name(tracker, publisher)
    assert "self" not in inspect.signature(tools["collect_field"]).parameters
    asyncio.run(tools["set_business_state"]("adhesion", "nouvelle_adhesion", .9, "Vous souhaitez adhérer.", "Est-ce une première adhésion ?"))
    assert publisher.states[-1]["conversation_id"] == tracker.conversation_id
    assert publisher.states[-1]["intent"]["reformulation"]
    assert publisher.states[-1]["state_version"] == 1


def test_payment_is_refused_and_finalization_has_summary():
    tracker, publisher = BusinessStateTracker(str(uuid4())), FakePublisher()
    tools = tools_by_name(tracker, publisher)
    asyncio.run(tools["refuse_action"]("payer une cotisation", "Les paiements sont interdits dans cette démonstration."))
    assert "paiement_demande" in publisher.states[-1]["risk_flags"]
    asyncio.run(tools["request_escalation"]("conseiller", "Paiement demandé", "Paiement refusé et orientation proposée."))
    asyncio.run(tools["finalize_call"]("L'appelant a demandé un paiement, refusé puis orienté."))
    assert publisher.states[-1]["is_final"] is True
    assert publisher.states[-1]["final_summary"]


def test_prompt_contains_catalogue_from_backend():
    instructions = build_instructions(PROCEDURES)
    assert "adhesion-qualification" in instructions
    assert "une question à la fois" in instructions
    assert "aucune opération réelle" in instructions
