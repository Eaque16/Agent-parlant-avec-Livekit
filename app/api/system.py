"""Routes d'état du service, catalogue de procédures et garde-fous du POC."""

from fastapi import APIRouter

from ..catalog import PROCEDURES
from ..config import settings
from ..integrations import AUTHORIZED_FUNCTIONS, FORBIDDEN_FUNCTIONS

router = APIRouter(tags=["système"])


@router.get("/health")
def health():
    provider_key = settings.google_api_key if settings.voice_provider == "google" else settings.openai_api_key
    return {
        "status": "ok",
        "mode": settings.voice_provider if provider_key else "demo",
        "voice_provider": settings.voice_provider,
        "demo_mode": settings.demo_mode,
        "integrations_enabled": False,
    }


@router.get("/api/procedures")
def procedures():
    return PROCEDURES


@router.get("/api/demo/capabilities")
def demo_capabilities():
    return {
        "data_policy": "fictitious_anonymized_only",
        "real_asaci_connections": False,
        "real_payments": False,
        "irreversible_actions": False,
        "authorized_future_functions": [vars(item) for item in AUTHORIZED_FUNCTIONS.values()],
        "forbidden_functions": sorted(FORBIDDEN_FUNCTIONS),
    }
