"""Worker LiveKit Agents : voix-à-voix en français avec Gemini Live ou OpenAI Realtime."""

import asyncio
import logging

import aiohttp
from livekit import agents
from livekit.agents import Agent, AgentSession
from livekit.plugins import google, openai

from .config import SUPPORTED_PROVIDERS, settings
from .prompts.asaci_agent_fr import build_instructions
from .state_publisher import StatePublisher
from .tools.business_tools import BusinessStateTracker, create_business_tools

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("asaci-voice-agent")

GREETING_INSTRUCTIONS = (
    "Accueille naturellement l'appelant en français : « Bonjour, je suis Awa, l'assistante virtuelle ASACI. "
    "Comment puis-je vous aider ? » Ne parle pas de simulation dans cet accueil."
)

# Références conservées pour que les tâches d'arrière-plan ne soient pas ramassées avant leur fin.
_background_tasks: set[asyncio.Task] = set()


def _spawn(coroutine) -> None:
    task = asyncio.create_task(coroutine)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _build_realtime_model():
    if settings.voice_provider == "google":
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY absente : ajoutez-la dans .env")
        return google.realtime.RealtimeModel(model=settings.google_model, voice=settings.google_voice)
    if settings.voice_provider == "openai":
        return openai.realtime.RealtimeModel(model=settings.openai_model, voice=settings.openai_voice)
    raise RuntimeError(
        f"VOICE_PROVIDER non pris en charge : {settings.voice_provider} (attendu : {', '.join(SUPPORTED_PROVIDERS)})"
    )


async def _persist_event(conversation_id: str, role: str, content: str, event_type: str) -> None:
    if not settings.agent_api_key:
        logger.warning("Événement non conservé : AGENT_INTERNAL_API_KEY absente")
        return
    url = f"{settings.api_base_url}/api/internal/conversations/{conversation_id}/agent-events"
    payload = {"role": role, "content": content, "event_type": event_type}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as client:
            async with client.post(url, headers={"X-Agent-Key": settings.agent_api_key}, json=payload) as response:
                if response.status >= 300:
                    logger.error("Conservation refusée (%s)", response.status)
    except (TimeoutError, aiohttp.ClientError):
        logger.exception("Échec de conservation de l'événement vocal")


async def _load_procedures() -> list[dict]:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as client:
        async with client.get(f"{settings.api_base_url}/api/procedures") as response:
            response.raise_for_status()
            return await response.json()


async def entrypoint(ctx: agents.JobContext) -> None:
    logger.info("Démarrage de l'agent pour la room %s", ctx.room.name)
    conversation_id = settings.conversation_id(ctx.room.name)
    if not conversation_id:
        raise RuntimeError("Room non reconnue : conversation introuvable")

    session = AgentSession(llm=_build_realtime_model())
    procedures = await _load_procedures()
    publisher = StatePublisher(ctx.room, conversation_id)
    tracker = BusinessStateTracker(conversation_id)
    tools = create_business_tools(tracker, publisher, procedures)

    @session.on("user_input_transcribed")
    def on_user_transcript(event) -> None:
        transcript = event.transcript.strip()
        if not transcript:
            return
        if event.is_final:
            _spawn(_persist_event(conversation_id, "user", transcript, "transcript"))
        else:
            _spawn(publisher.publish_partial_transcript(transcript))

    @session.on("conversation_item_added")
    def on_conversation_item(event) -> None:
        item = event.item
        content = getattr(item, "text_content", "")
        if getattr(item, "role", None) == "assistant" and content:
            _spawn(_persist_event(conversation_id, "assistant", content, "agent_reply"))

    @session.on("error")
    def on_error(event) -> None:
        _spawn(_persist_event(conversation_id, "system", str(event.error), "error"))

    await session.start(room=ctx.room, agent=Agent(instructions=build_instructions(procedures), tools=tools))
    await session.generate_reply(instructions=GREETING_INSTRUCTIONS)


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
