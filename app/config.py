"""Configuration lue depuis l'environnement (et `.env` hors tests)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() == "true"


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_path: str = os.getenv("DATABASE_PATH", "./data/asaci.db")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    retention_days: int = int(os.getenv("RETENTION_DAYS", "90"))

    # Fournisseurs IA
    voice_provider: str = os.getenv("VOICE_PROVIDER", "google").strip().lower()
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    google_api_key: str | None = os.getenv("GOOGLE_API_KEY") or None
    chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
    transcribe_model: str = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
    tts_model: str = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    tts_voice: str = os.getenv("OPENAI_TTS_VOICE", "coral")

    # Garde-fous du POC
    demo_mode: bool = _flag("DEMO_MODE", "true")
    integrations_enabled: bool = _flag("INTEGRATIONS_ENABLED", "false")
    integration_base_url: str | None = os.getenv("INTEGRATION_BASE_URL") or None
    integration_api_token: str | None = os.getenv("INTEGRATION_API_TOKEN") or None

    # Secrets d'accès
    admin_api_key: str = os.getenv("ADMIN_API_KEY", "demo-admin-key")
    agent_internal_api_key: str | None = os.getenv("AGENT_INTERNAL_API_KEY") or None
    internal_api_key: str | None = os.getenv("INTERNAL_API_KEY") or None

    # LiveKit Cloud
    livekit_url: str | None = os.getenv("LIVEKIT_URL") or None
    livekit_api_key: str | None = os.getenv("LIVEKIT_API_KEY") or None
    livekit_api_secret: str | None = os.getenv("LIVEKIT_API_SECRET") or None
    livekit_token_ttl_seconds: int = min(int(os.getenv("LIVEKIT_TOKEN_TTL_SECONDS", "300")), 600)
    livekit_room_prefix: str = "asaci-demo-"


settings = Settings()
