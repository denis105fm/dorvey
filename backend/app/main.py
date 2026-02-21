"""
Dorvey - Smart Doorway Generation System
Backend FastAPI Application
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func

from app.api import (
    auth, campaigns, doorways, servers, domains, templates, keywords,
    deploy, indexing, analytics, optimizer, offers, webhooks,
    settings as settings_router, cron, clustering, copy_winners,
    seo, broken_links_api, rules, billing, users_admin,
)
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserRole


async def ensure_default_admin():
    """Create default admin if no users exist (first deploy)."""
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(func.count(User.id)))
        if (r.scalar() or 0) > 0:
            return
        admin = User(
            email=settings.DEFAULT_ADMIN_EMAIL,
            password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
            role=UserRole.ADMIN.value,
        )
        db.add(admin)
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_default_admin()
    yield


app = FastAPI(
    title="Dorvey API",
    description="Система умных дорвеев с AI-оптимизацией",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


def _instruction_path() -> Path:
    """Path to instruction.md inside app package (always deployed with backend)."""
    app_dir = Path(__file__).resolve().parent
    return app_dir / "static" / "instruction.md"


@app.get("/api/docs/instruction", response_class=PlainTextResponse)
def get_instruction():
    """Return instruction markdown for in-app help."""
    path = _instruction_path()
    if not path.exists():
        return PlainTextResponse(content="# Инструкция\n\nФайл инструкции не найден.", status_code=404)
    return PlainTextResponse(content=path.read_text(encoding="utf-8"))


def _images_dir() -> Path:
    """Path to instruction images (SVG placeholders)."""
    return Path(__file__).resolve().parent / "static" / "images"


@app.get("/api/docs/images/{filename}")
def get_instruction_image(filename: str):
    """Serve instruction images (placeholders or user screenshots). Safe: only .png, .jpg, .svg."""
    if not filename or ".." in filename or "/" in filename:
        raise HTTPException(404, "Not found")
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    if ext not in ("png", "jpg", "jpeg", "svg"):
        raise HTTPException(404, "Not found")
    path = _images_dir() / filename
    if not path.exists():
        raise HTTPException(404, "Not found")
    media = "image/svg+xml" if ext == "svg" else f"image/{ext}" if ext != "jpg" else "image/jpeg"
    return FileResponse(path, media_type=media)


# API Routes
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(doorways.router, prefix="/api/doorways", tags=["doorways"])
app.include_router(servers.router, prefix="/api/servers", tags=["servers"])
app.include_router(domains.router, prefix="/api/domains", tags=["domains"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(keywords.router, prefix="/api/keywords", tags=["keywords"])
app.include_router(deploy.router, prefix="/api/deploy", tags=["deploy"])
app.include_router(indexing.router, prefix="/api/indexing", tags=["indexing"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(optimizer.router, prefix="/api/optimizer", tags=["optimizer"])
app.include_router(offers.router, prefix="/api/offers", tags=["offers"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(cron.router, prefix="/api/cron", tags=["cron"])
app.include_router(clustering.router, prefix="/api/clustering", tags=["clustering"])
app.include_router(copy_winners.router, prefix="/api/copy", tags=["copy"])
app.include_router(seo.router, prefix="/api/seo", tags=["seo"])
app.include_router(broken_links_api.router, prefix="/api/broken-links", tags=["broken-links"])
app.include_router(rules.router, prefix="/api/rules", tags=["rules"])
app.include_router(billing.router, prefix="/api/billing", tags=["billing"])
app.include_router(users_admin.router, prefix="/api/users", tags=["users"])
