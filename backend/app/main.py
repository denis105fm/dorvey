"""
Dorvey - Smart Doorway Generation System
Backend FastAPI Application
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func

from app.api import (
    auth, campaigns, doorways, servers, domains, templates, keywords,
    deploy, indexing, analytics, optimizer, offers, webhooks,
    settings as settings_router, cron, clustering, copy_winners,
    seo, broken_links_api, rules, billing, users_admin,
)
from app.core.config import settings

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
