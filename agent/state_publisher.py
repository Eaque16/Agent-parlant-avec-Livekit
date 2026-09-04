import asyncio
import json
import logging
import os

import aiohttp


logger = logging.getLogger("asaci-state-publisher")


class StatePublisher:
    def __init__(self, room, conversation_id: str):
        self.room = room
        self.conversation_id = conversation_id
        self.base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:8000").rstrip("/")
        self.internal_key = os.getenv("INTERNAL_API_KEY")

    async def publish_topic(self, topic: str, payload: dict) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        await self.room.local_participant.publish_data(encoded, reliable=True, topic=topic)

    async def _post_backend(self, state: dict) -> dict:
        if not self.internal_key:
            return {"ok": False, "error": "INTERNAL_API_KEY absente"}
        url = f"{self.base_url}/internal/conversations/{self.conversation_id}/state"
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as client:
                    async with client.post(url, json=state, headers={"X-Internal-Key": self.internal_key}) as response:
                        if response.status < 300:
                            return {"ok": True, "state": await response.json()}
                        detail = await response.text()
                        if response.status < 500:
                            return {"ok": False, "status": response.status, "error": detail[:300]}
            except (aiohttp.ClientError, asyncio.TimeoutError):
                pass
            if attempt < 2:
                await asyncio.sleep(.2 * (2 ** attempt))
        return {"ok": False, "error": "backend indisponible après réessais"}

    async def publish_state(self, state: dict) -> dict:
        livekit_task = asyncio.create_task(self.publish_topic("business_state", state))
        backend_task = asyncio.create_task(self._post_backend(state))
        livekit_result, backend_result = await asyncio.gather(livekit_task, backend_task, return_exceptions=True)
        return {
            "livekit_ok": not isinstance(livekit_result, Exception),
            "backend": backend_result if not isinstance(backend_result, Exception) else {"ok": False, "error": "publication impossible"},
        }

    async def publish_partial_transcript(self, transcript: str) -> None:
        await self.publish_topic("transcript_partial", {"conversation_id": self.conversation_id, "text": transcript, "is_final": False})
