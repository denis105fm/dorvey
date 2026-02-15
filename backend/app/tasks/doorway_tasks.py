"""Celery tasks for doorway generation and deploy."""

import asyncio
from app.celery_app import celery_app


@celery_app.task
def generate_doorway_async(campaign_id: int, domain_id: int, keyword: str, path: str = "/"):
    """Run doorway generation in background."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings
    from app.services.generator import generate_doorway
    from app.models.doorway import Doorway, DoorwayVersion

    async def run():
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            result = await generate_doorway(
                db, campaign_id=campaign_id, domain_id=domain_id, keyword=keyword, path=path
            )
            dw = Doorway(
                campaign_id=campaign_id, domain_id=domain_id, path=path,
                title=result.get("title"), content=result.get("content"),
                meta_description=result.get("meta_description"), status="draft",
            )
            db.add(dw)
            await db.flush()
            db.add(DoorwayVersion(doorway_id=dw.id, content_snapshot={
                "title": dw.title, "content": dw.content, "meta_description": dw.meta_description,
            }))
            await db.commit()
            return {"status": "ok", "doorway_id": dw.id}

    try:
        return asyncio.run(run())
    except Exception as e:
        return {"status": "error", "message": str(e)}


@celery_app.task
def deploy_doorway_async(doorway_id: int):
    """Run deploy in background."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from app.core.config import settings
    from app.models.doorway import Doorway
    from app.models.domain import Domain
    from app.models.server import Server
    from app.models.setting import Setting
    from app.models.campaign import Campaign
    from app.services.deploy import deploy_doorway_sync, prepare_doorway_html, run_certbot_ssl
    from datetime import datetime

    async def run():
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            html = await prepare_doorway_html(db, doorway_id)
            if not html:
                return {"status": "error", "message": "Could not prepare HTML"}
            r = await db.execute(
                select(Doorway, Domain, Server)
                .join(Domain, Doorway.domain_id == Domain.id)
                .join(Server, Domain.server_id == Server.id)
                .where(Doorway.id == doorway_id)
            )
            row = r.first()
            if not row:
                return {"status": "error", "message": "Not found"}
            dw, dom, srv = row
            ok, msg = deploy_doorway_sync(srv, dom.domain, dw.path or "/", html, srv.path)
            if not ok:
                return {"status": "error", "message": msg}
            if getattr(srv, "auth_type", None) != "ftp":
                camp_r = await db.execute(select(Campaign).where(Campaign.id == dw.campaign_id))
                camp = camp_r.scalar_one_or_none()
                if camp:
                    set_r = await db.execute(
                        select(Setting).where(
                            Setting.user_id == camp.user_id,
                            Setting.key == "ssl_auto_enabled",
                        )
                    )
                    ssl_set = set_r.scalar_one_or_none()
                    if ssl_set and str(ssl_set.value or "").lower() == "true":
                        run_certbot_ssl(srv, dom.domain, srv.path or "/var/www/html")
            dw.status = "deployed"
            dw.deployed_at = datetime.utcnow()
            await db.commit()
            return {"status": "ok", "message": msg}

    try:
        return asyncio.run(run())
    except Exception as e:
        return {"status": "error", "message": str(e)}


@celery_app.task
def deploy_batch_with_stagger(
    doorway_ids: list[int],
    min_delay_sec: float = 30,
    max_delay_sec: float = 180,
):
    """
    Deploy multiple doorways with staggered delays (anti-detection).
    Prevents mass synchronous publishes.
    """
    from app.services.anti_detection import StaggerConfig, sleep_for_stagger

    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from app.core.config import settings
    from app.models.doorway import Doorway
    from app.models.domain import Domain
    from app.models.server import Server
    from app.models.campaign import Campaign
    from app.services.deploy import deploy_doorway_sync, prepare_doorway_html, run_certbot_ssl
    from datetime import datetime

    cfg = StaggerConfig(min_delay_sec=min_delay_sec, max_delay_sec=max_delay_sec)
    results: list = []
    total = len(doorway_ids)

    async def run():
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            for i, dw_id in enumerate(doorway_ids):
                sleep_for_stagger(i, total, cfg)
                html = await prepare_doorway_html(db, dw_id)
                if not html:
                    results.append({"doorway_id": dw_id, "ok": False, "msg": "Could not prepare HTML"})
                    continue
                r = await db.execute(
                    select(Doorway, Domain, Server)
                    .join(Domain, Doorway.domain_id == Domain.id)
                    .join(Server, Domain.server_id == Server.id)
                    .where(Doorway.id == dw_id)
                )
                row = r.first()
                if not row:
                    results.append({"doorway_id": dw_id, "ok": False, "msg": "Not found"})
                    continue
                dw, dom, srv = row
                ok, msg = deploy_doorway_sync(srv, dom.domain, dw.path or "/", html, srv.path)
                if not ok:
                    results.append({"doorway_id": dw_id, "ok": False, "msg": msg})
                    continue
                if getattr(srv, "auth_type", None) != "ftp":
                    camp_r = await db.execute(select(Campaign).where(Campaign.id == dw.campaign_id))
                    camp = camp_r.scalar_one_or_none()
                    if camp:
                        set_r = await db.execute(
                            select(Setting).where(
                                Setting.user_id == camp.user_id,
                                Setting.key == "ssl_auto_enabled",
                            )
                        )
                        ssl_set = set_r.scalar_one_or_none()
                        if ssl_set and str(ssl_set.value or "").lower() == "true":
                            run_certbot_ssl(srv, dom.domain, srv.path or "/var/www/html")
                dw.status = "deployed"
                dw.deployed_at = datetime.utcnow()
                results.append({"doorway_id": dw_id, "ok": True, "msg": msg})
            await db.commit()
        return {"status": "ok", "results": results}

    try:
        return asyncio.run(run())
    except Exception as e:
        return {"status": "error", "message": str(e), "results": results}


@celery_app.task
def cron_run_all():
    """Run all daily cron tasks. Call via Celery Beat."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings
    from app.services.cron_runner import run_all

    async def _run():
        engine = create_async_engine(settings.DATABASE_URL)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as db:
            return await run_all(db)

    try:
        return asyncio.run(_run())
    except Exception as e:
        return {"status": "error", "message": str(e)}


@celery_app.task
def auto_generate_from_keywords(max_per_run: int = 20):
    """
    Auto-generate doorways from campaign keywords.
    Campaigns with affiliate_rules.auto_generate_enabled=true.
    For each such campaign: pick keywords without doorway, generate (limit 5 per campaign).
    """
    import asyncio
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings
    from app.models.campaign import Campaign
    from app.models.domain import Domain
    from app.models.keyword import Keyword
    from app.models.doorway import Doorway
    from app.services.generator import generate_doorway
    from app.models.doorway import DoorwayVersion

    async def _run():
        engine = create_async_engine(settings.DATABASE_URL)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as db:
            r = await db.execute(
                select(Campaign.id, Campaign.affiliate_rules)
                .where(Campaign.status == "active")
            )
            campaigns = [(row[0], (row[1] or {}).get("auto_generate_enabled")) for row in r.all()]
            generated = 0
            for camp_id, auto_enabled in campaigns:
                if not auto_enabled:
                    continue
                if generated >= max_per_run:
                    break
                domains_r = await db.execute(
                    select(Domain.id).where(Domain.campaign_id == camp_id)
                )
                domain_ids = [row[0] for row in domains_r.all()]
                if not domain_ids:
                    continue
                keywords_r = await db.execute(
                    select(Keyword.id, Keyword.keyword).where(Keyword.campaign_id == camp_id)
                )
                keywords = list(keywords_r.all())
                limit_this_campaign = min(5, max_per_run - generated)
                path_slug = lambda t: "/" + t.lower().replace(" ", "-").replace("'", "")[:60].rstrip("-")
                for kw_id, kw_text in keywords[:limit_this_campaign * 3]:
                    if generated >= limit_this_campaign:
                        break
                    path = path_slug(kw_text)
                    for domain_id in domain_ids[:1]:
                        exists = await db.execute(
                            select(Doorway.id).where(
                                Doorway.campaign_id == camp_id,
                                Doorway.domain_id == domain_id,
                                Doorway.path == path,
                            )
                        )
                        if exists.first():
                            continue
                        try:
                            result = await generate_doorway(
                                db, campaign_id=camp_id, domain_id=domain_id, keyword=kw_text, path=path
                            )
                            dw = Doorway(
                                campaign_id=camp_id, domain_id=domain_id, path=path,
                                title=result.get("title"), content=result.get("content"),
                                meta_description=result.get("meta_description"), status="draft",
                            )
                            db.add(dw)
                            await db.flush()
                            db.add(DoorwayVersion(
                                doorway_id=dw.id,
                                content_snapshot={
                                    "title": dw.title, "content": dw.content,
                                    "meta_description": dw.meta_description,
                                },
                            ))
                            await db.commit()
                            generated += 1
                            if generated >= limit_this_campaign:
                                break
                        except Exception:
                            await db.rollback()
                            continue
            return {"status": "ok", "generated": generated}

    try:
        return asyncio.run(_run())
    except Exception as e:
        return {"status": "error", "message": str(e)}
