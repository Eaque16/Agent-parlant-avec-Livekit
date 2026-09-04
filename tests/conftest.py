"""Configuration commune des tests : environnement isolé, base temporaire et fixtures."""

import atexit
import os
import shutil
import tempfile
from pathlib import Path

# Les réglages sont lus à l'import de `app` : l'environnement doit être fixé avant.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="asaci-tests-"))
atexit.register(shutil.rmtree, _TMP_DIR, True)
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_PATH"] = str(_TMP_DIR / "asaci-test.db")
for name in (
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "INTERNAL_API_KEY",
    "AGENT_INTERNAL_API_KEY",
    "PUBLIC_BASE_URL",
):
    os.environ.pop(name, None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

INTERNAL_KEY = "test-internal"
AGENT_KEY = "test-agent-secret"


@pytest.fixture
def override_settings():
    """Modifie temporairement des réglages (dataclass figée) et les restaure en fin de test."""
    originals: dict[str, object] = {}

    def _apply(**values):
        for name, value in values.items():
            originals.setdefault(name, getattr(settings, name))
            object.__setattr__(settings, name, value)

    yield _apply
    for name, value in originals.items():
        object.__setattr__(settings, name, value)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def conversation_id(client) -> str:
    return client.post("/api/conversations", json={"channel": "web"}).json()["id"]


@pytest.fixture
def internal_key(override_settings) -> str:
    override_settings(internal_api_key=INTERNAL_KEY)
    return INTERNAL_KEY


@pytest.fixture
def agent_key(override_settings) -> str:
    override_settings(agent_internal_api_key=AGENT_KEY)
    return AGENT_KEY
