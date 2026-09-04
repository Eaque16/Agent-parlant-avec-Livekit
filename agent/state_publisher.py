"""Publication des états métier vers la room LiveKit et vers le backend FastAPI."""

import asyncio
import json
import logging

import aiohttp

from .config import settings

logger = logging.getLogger("asaci-state-publisher")

BACKEND_TIMEOUT = aiohttp.ClientTimeout(total=4)
BACKEND_ATTEMPTS = 3


class StatePublisher:
    def __init__(self, room, conversation_id: str) -> None:
        self.room = room
        self.conversation_id = conversation_id

    async def publish_topic(self, topic: str, payload: dict) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        await self.room.local_participant.publish_data(encoded, reliable=True, topic=topic)

    async def _post_backend(self, state: dict) -> dict:
        if not settings.internal_api_key:
            return {"ok": False, "error": "INTERNAL_API_KEY absente"}
        url = f"{settings.api_base_url}/internal/conversations/{self.conversation_id}/state"
        headers = {"X-Internal-Key": settings.internal_api_key}
        for attempt in range(BACKEND_ATTEMPTS):
            try:
                async with aiohttp.ClientSession(timeout=BACKEND_TIMEOUT) as client:
                    async with client.post(url, json=state, headers=headers) as response:
                        if response.status < 300:
                            return {"ok": True, "state": await response.json()}
                        detail = await response.text()
                        if response.status < 500:
                            return {"ok": False, "status": response.status, "error": detail[:300]}
            except (TimeoutError, aiohttp.ClientError):
                logger.warning("Backend injoignable (tentative %s/%s)", attempt + 1, BACKEND_ATTEMPTS)
            if attempt < BACKEND_ATTEMPTS - 1:
                await asyncio.sleep(0.2 * (2**attempt))
        return {"ok": False, "error": "backend indisponible après réessais"}

    async def publish_state(self, state: dict) -> dict:
        livekit_result, backend_result = await asyncio.gather(
            self.publish_topic("business_state", state),
            self._post_backend(state),
            return_exceptions=True,
        )
        if isinstance(livekit_result, Exception):
            logger.warning("Diffusion LiveKit impossible : %s", livekit_result)
        if isinstance(backend_result, Exception):
            logger.warning("Publication backend impossible : %s", backend_result)
            backend_result = {"ok": False, "error": "publication impossible"}
        return {"livekit_ok": not isinstance(livekit_result, Exception), "backend": backend_result}

    async def publish_partial_transcript(self, transcript: str) -> None:
        payload = {"conversation_id": self.conversation_id, "text": transcript, "is_final": False}
        await self.publish_topic("transcript_partial", payload)
