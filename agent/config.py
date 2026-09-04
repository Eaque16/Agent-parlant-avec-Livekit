"""Configuration du worker vocal, lue depuis l'environnement (et `.env` hors tests)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

SUPPORTED_PROVIDERS = ("google", "openai")


@dataclass(frozen=True)
class AgentSettings:
    api_base_url: str = os.getenv("AGENT_API_BASE_URL", "http://localhost:8000").rstrip("/")
    agent_api_key: str | None = os.getenv("AGENT_INTERNAL_API_KEY") or None
    internal_api_key: str | None = os.getenv("INTERNAL_API_KEY") or None
    room_prefix: str = "asaci-demo-"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    voice_provider: str = os.getenv("VOICE_PROVIDER", "google").strip().lower()
    google_api_key: str | None = os.getenv("GOOGLE_API_KEY") or None
    google_model: str = os.getenv("GOOGLE_REALTIME_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")
    google_voice: str = os.getenv("GOOGLE_REALTIME_VOICE", "Puck")
    openai_model: str = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime")
    openai_voice: str = os.getenv("OPENAI_REALTIME_VOICE", "coral")

    def conversation_id(self, room_name: str) -> str | None:
        """Retrouve l'identifiant de conversation encodé dans le nom de la room LiveKit."""
        if not room_name.startswith(self.room_prefix):
            return None
        return room_name[len(self.room_prefix) :]


settings = AgentSettings()
