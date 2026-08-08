"""FastAPI application factory."""
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import poller as pipeline_poller
from .config import get_settings
from .db import dispose_db, init_db, session_factory
from .routers import account, applications, auth, billing, cvs, documents, generate, latex, templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("cvglowup")

# Per-IP sliding-window rate limits: route prefix -> (max requests, window seconds)
_RATE_LIMITS = {
    "/api/auth/": (20, 60),
    "/api/generate": (12, 60),
    "/api/byok/validate": (6, 60),
    "/api/documents": (120, 60),
    "/api/feedback": (5, 60),
}
_hits: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    settings = get_settings()
    log.info(
        "cvglowup up — env=%s ai=%s billing=%s latex=%s typst=%s",
        settings.env,
        "gemini" if settings.ai_enabled else "offline-fake",
        settings.billing_enabled,
        settings.latex_enabled,
        settings.typst_command,
    )
    reaper = None
    if settings.latex_enabled and settings.is_prod and settings.latexc_idle_off_minutes > 0:
        import asyncio

        reaper = asyncio.create_task(latex.idle_reaper())
    poll_task = None
    if not settings.is_prod and (settings.ft_client_id or settings.adzuna_app_id):
        import asyncio as _asyncio

        poll_task = _asyncio.create_task(pipeline_poller.poll_loop())
    yield
    if reaper is not None:
        reaper.cancel()
    if poll_task is not None:
        poll_task.cancel()
    await dispose_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CV Glowup", version="2.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path

        # CSRF hardening: cross-origin browser writes are rejected.
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and path != "/api/billing/webhook":
            origin = request.headers.get("origin")
            if origin:
                base = f"{urlparse(origin).scheme}://{urlparse(origin).netloc}"
                host_origin = f"{request.url.scheme}://{request.url.netloc}"
                if base != host_origin and base not in settings.origins:
                    return JSONResponse({"detail": "Origin not allowed."}, status_code=403)

        # Rate limiting on sensitive routes.
        for prefix, (limit, window) in _RATE_LIMITS.items():
            if path.startswith(prefix) and request.method != "GET":
                key = f"{_client_ip(request)}|{prefix}"
                now = time.monotonic()
                q = _hits[key]
                while q and now - q[0] > window:
                    q.popleft()
                if len(q) >= limit:
                    return JSONResponse(
                        {"detail": "Too many requests. Slow down a little."}, status_code=429
                    )
                q.append(now)
                break

        return await call_next(request)

    app.include_router(auth.router)
    app.include_router(account.router)
    app.include_router(cvs.router)
    app.include_router(generate.router)
    app.include_router(documents.router)
    app.include_router(billing.router)
    app.include_router(latex.router)
    app.include_router(templates.router)
    app.include_router(applications.router)
    app.include_router(pipeline_poller.internal_router)

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    # Deploy smoke checks hit this one: Google's edge intercepts /healthz on
    # *.run.app URLs before it reaches the container, /api/* always gets through.
    @app.get("/api/healthz")
    async def api_healthz():
        try:
            async with session_factory()() as session:
                await session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            log.exception("healthz database ping failed")
            db_ok = False
        return JSONResponse({"ok": db_ok, "db": db_ok}, status_code=200 if db_ok else 503)

    # ---- SPA serving (production build) ------------------------------------
    dist: Path = settings.frontend_dist
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}")
        async def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            file = dist / path
            if path and file.is_file():
                return FileResponse(file)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
