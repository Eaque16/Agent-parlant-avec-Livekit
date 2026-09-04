import logging
import os
import asyncio

import aiohttp
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentSession
from livekit.plugins import google, openai

from .prompts.asaci_agent_fr import build_instructions
from .state_publisher import StatePublisher
from .tools.business_tools import BusinessStateTracker, create_business_tools

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("asaci-voice-agent")


def _conversation_id(room_name: str) -> str | None:
    prefix = "asaci-demo-"
    return room_name[len(prefix):] if room_name.startswith(prefix) else None


async def _persist_event(conversation_id: str, role: str, content: str, event_type: str) -> None:
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:8000").rstrip("/")
    key = os.getenv("AGENT_INTERNAL_API_KEY")
    if not key:
        logger.warning("Événement non conservé : AGENT_INTERNAL_API_KEY absent")
        return
    url = f"{base_url}/api/internal/conversations/{conversation_id}/agent-events"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as client:
            async with client.post(url, headers={"X-Agent-Key": key},
                                   json={"role": role, "content": content, "event_type": event_type}) as response:
                if response.status >= 300:
                    logger.error("Conservation refusée (%s)", response.status)
    except Exception:
        logger.exception("Échec de conservation de l'événement vocal")


async def _load_procedures() -> list[dict]:
    url = os.getenv("AGENT_API_BASE_URL", "http://localhost:8000").rstrip("/") + "/api/procedures"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as client:
        async with client.get(url) as response:
            response.raise_for_status()
            return await response.json()


class AsaciVoiceAgent(Agent):
    def __init__(self, instructions: str, tools: list) -> None:
        super().__init__(instructions=instructions, tools=tools)


async def entrypoint(ctx: agents.JobContext) -> None:
    logger.info("Démarrage de l'agent pour la room %s", ctx.room.name)
    provider = os.getenv("VOICE_PROVIDER", "google").lower()
    if provider == "google":
        if not os.getenv("GOOGLE_API_KEY"):
            raise RuntimeError("GOOGLE_API_KEY absente : ajoutez-la dans .env")
        realtime_model = google.realtime.RealtimeModel(
            model=os.getenv("GOOGLE_REALTIME_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025"),
            voice=os.getenv("GOOGLE_REALTIME_VOICE", "Puck"),
        )
    elif provider == "openai":
        realtime_model = openai.realtime.RealtimeModel(
            model=os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime"),
            voice=os.getenv("OPENAI_REALTIME_VOICE", "coral"),
        )
    else:
        raise RuntimeError(f"VOICE_PROVIDER non pris en charge : {provider}")
    session = AgentSession(llm=realtime_model)
    conversation_id = _conversation_id(ctx.room.name)
    if not conversation_id:
        raise RuntimeError("Room non reconnue : conversation introuvable")
    procedures = await _load_procedures()
    publisher = StatePublisher(ctx.room, conversation_id)
    tracker = BusinessStateTracker(conversation_id)
    tools = create_business_tools(tracker, publisher, procedures)

    @session.on("user_input_transcribed")
    def on_user_transcript(event) -> None:
        transcript = event.transcript.strip()
        if transcript and event.is_final:
            asyncio.create_task(_persist_event(conversation_id, "user", transcript, "transcript"))
        elif transcript:
            asyncio.create_task(publisher.publish_partial_transcript(transcript))

    @session.on("conversation_item_added")
    def on_conversation_item(event) -> None:
        item = event.item
        if conversation_id and getattr(item, "role", None) == "assistant":
            content = getattr(item, "text_content", "")
            if content:
                asyncio.create_task(_persist_event(conversation_id, "assistant", content, "agent_reply"))

    @session.on("error")
    def on_error(event) -> None:
        if conversation_id:
            asyncio.create_task(_persist_event(conversation_id, "system", str(event.error), "error"))
    await session.start(room=ctx.room, agent=AsaciVoiceAgent(build_instructions(procedures), tools))
    await session.generate_reply(
        instructions="Accueille naturellement l'appelant en français : « Bonjour, je suis Awa, l'assistante virtuelle ASACI. Comment puis-je vous aider ? » Ne parle pas de simulation dans cet accueil."
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
