import logging
import os
import asyncio

import aiohttp

from livekit import agents
from livekit.agents import Agent, AgentSession
from livekit.plugins import openai

from .prompt import VOICE_AGENT_PROMPT

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


class AsaciVoiceAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=VOICE_AGENT_PROMPT)


async def entrypoint(ctx: agents.JobContext) -> None:
    logger.info("Démarrage de l'agent pour la room %s", ctx.room.name)
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            model=os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime"),
            voice=os.getenv("OPENAI_REALTIME_VOICE", "coral"),
        )
    )
    conversation_id = _conversation_id(ctx.room.name)

    @session.on("user_input_transcribed")
    def on_user_transcript(event) -> None:
        if conversation_id and event.is_final and event.transcript.strip():
            asyncio.create_task(_persist_event(conversation_id, "user", event.transcript.strip(), "transcript"))

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
    await session.start(room=ctx.room, agent=AsaciVoiceAgent())
    await session.generate_reply(
        instructions="Accueille l'appelant en français et rappelle en une phrase qu'il s'agit d'une démonstration fictive."
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
