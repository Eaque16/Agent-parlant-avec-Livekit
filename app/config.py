from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_path: str = os.getenv("DATABASE_PATH", "./data/asaci.db")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
    transcribe_model: str = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
    tts_model: str = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    tts_voice: str = os.getenv("OPENAI_TTS_VOICE", "coral")
    admin_api_key: str = os.getenv("ADMIN_API_KEY", "demo-admin-key")
    retention_days: int = int(os.getenv("RETENTION_DAYS", "90"))
    demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
    integrations_enabled: bool = os.getenv("INTEGRATIONS_ENABLED", "false").lower() == "true"
    integration_base_url: str | None = os.getenv("INTEGRATION_BASE_URL") or None
    integration_api_token: str | None = os.getenv("INTEGRATION_API_TOKEN") or None
    livekit_url: str | None = os.getenv("LIVEKIT_URL") or None
    livekit_api_key: str | None = os.getenv("LIVEKIT_API_KEY") or None
    livekit_api_secret: str | None = os.getenv("LIVEKIT_API_SECRET") or None
    livekit_token_ttl_seconds: int = min(int(os.getenv("LIVEKIT_TOKEN_TTL_SECONDS", "300")), 600)
    agent_internal_api_key: str | None = os.getenv("AGENT_INTERNAL_API_KEY") or None
    internal_api_key: str | None = os.getenv("INTERNAL_API_KEY") or None


settings = Settings()
