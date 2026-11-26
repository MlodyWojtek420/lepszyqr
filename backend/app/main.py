from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import auth, config, models  # noqa: F401  (models rejestruje tabele)
from .db import Base, engine
from .routes_badges import router as badges_router, start_browser, stop_browser
from .routes_export import router as export_router
from .routes_import import router as import_router
from .routes_volunteers import router as volunteers_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    Base.metadata.create_all(engine)
    await start_browser()
    yield
    await stop_browser()


app = FastAPI(title="qr gen", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.include_router(auth.router)
app.include_router(volunteers_router)
app.include_router(import_router)
app.include_router(badges_router)
app.include_router(export_router)


@app.get("/api/health")
def health():
    return {"ok": True}
