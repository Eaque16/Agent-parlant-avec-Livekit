"""Point d'entrée FastAPI : cycle de vie, routeurs et interface React compilée."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import database as db
from .api import ROUTERS

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    db.purge_expired()
    yield


app = FastAPI(title="Agent vocal ASACI", version="0.2.0", lifespan=lifespan)
for router in ROUTERS:
    app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
@app.get("/conformite", include_in_schema=False)
def spa_entrypoint():
    return FileResponse(STATIC_DIR / "index.html")
