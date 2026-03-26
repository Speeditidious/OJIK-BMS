"""OJIK BMS FastAPI application entry point."""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.routers import (
    admin,
    analysis,
    auth,
    custom,
    fumens,
    schedules,
    scores,
    sync,
    tables,
    users,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown logic."""
    await _seed_default_tables()
    yield
    from app.core.database import engine
    await engine.dispose()


async def _seed_default_tables() -> None:
    """Create DifficultyTable rows for all default tables defined in config.json.

    Only inserts rows that don't already exist (matched by source_url).
    Does NOT fetch remote data — that's the Celery task's job.
    """
    import logging

    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.difficulty_table import DifficultyTable
    from app.parsers.table_fetcher import get_default_table_configs

    logger = logging.getLogger(__name__)

    default_configs = get_default_table_configs()
    if not default_configs:
        return

    try:
        async with AsyncSessionLocal() as db:
            for cfg in default_configs:
                url: str = cfg.get("url", "")
                if not url:
                    continue

                result = await db.execute(
                    select(DifficultyTable).where(DifficultyTable.source_url == url)
                )
                if result.scalar_one_or_none() is not None:
                    continue  # already seeded

                table = DifficultyTable(
                    name=cfg.get("name", url),
                    symbol=cfg.get("symbol"),
                    slug=cfg.get("slug"),
                    source_url=url,
                    is_default=True,
                )
                db.add(table)
                logger.info(f"Seeded default table: {cfg.get('name')}")

            await db.commit()
    except Exception as exc:
        # Don't crash the app if seeding fails (e.g. DB not ready yet)
        import logging as _logging
        _logging.getLogger(__name__).warning(f"Default table seeding failed: {exc}")


app = FastAPI(
    title="OJIK BMS API",
    description="Backend API for OJIK BMS - BMS rhythm game companion service",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# SessionMiddleware is required by sqladmin's authentication backend.
# Starlette applies middleware in LIFO order, so SessionMiddleware (added
# second) wraps the outermost layer and runs first on each request.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=3600 * 8,
    same_site="lax",
    https_only=False,  # Set to True when deploying with HTTPS
)

# ── Routers ─────────────────────────────────────────────────────────────────

app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tables.router)
app.include_router(scores.router)
app.include_router(fumens.router)
app.include_router(analysis.router)
app.include_router(custom.router)
app.include_router(sync.router)
app.include_router(schedules.router)


# ── Static files ────────────────────────────────────────────────────────────

_UPLOADS_DIR = Path(settings.UPLOADS_DIR)
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_UPLOADS_DIR)), name="uploads")

# ── Admin panel ─────────────────────────────────────────────────────────────
# Must be mounted after routers and static files so /admin does not clash.

from app.admin import create_admin  # noqa: E402
from app.core.database import engine as _engine  # noqa: E402

_admin = create_admin(app, _engine)

# ── Health check ────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
