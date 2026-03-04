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
    from app.services.deploy import deploy_doorway_sync, prepare_doorway_html, run_certbot_ssl, deploy_sw_push, deploy_sitemap_robots_sync
    from datetime import datetime

    async def run():
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            html = await prepare_doorway_html(db, doorway_id, for_bot=False)
            if not html:
                return {"status": "error", "message": "Could not prepare HTML"}
            r = await db.execute(
                select(Doorway, Domain, Server, Campaign)
                .join(Domain, Doorway.domain_id == Domain.id)
                .join(Server, Domain.server_id == Server.id)
                .join(Campaign, Doorway.campaign_id == Campaign.id)
                .where(Doorway.id == doorway_id)
            )
            row = r.first()
            if not row:
                return {"status": "error", "message": "Not found"}
            dw, dom, srv, camp = row
            ok, msg = deploy_doorway_sync(srv, dom.domain, dw.path or "/", html, srv.path)
            camp_cloaking = (camp.affiliate_rules or {}).get("cloaking") or {}
            dw_cloaking = (dw.cloaking_rules or {}).get("cloaking") or {}
            cloaking_enabled = (isinstance(camp_cloaking, dict) and camp_cloaking.get("enabled")) or (isinstance(dw_cloaking, dict) and dw_cloaking.get("enabled")) or bool((dw.cloaking_rules or {}).get("cloaking_enabled"))
            if ok and cloaking_enabled:
                html_seo = await prepare_doorway_html(db, doorway_id, for_bot=True)
                if html_seo:
                    ok2, _ = deploy_doorway_sync(srv, dom.domain, dw.path or "/", html_seo, srv.path, remote_suffix=".seo")
            if not ok:
                return {"status": "error", "message": msg}
            if getattr(srv, "auth_type", None) != "ftp":
                camp_r = await db.execute(select(Campaign).where(Campaign.id == dw.campaign_id))
                camp = camp_r.scalar_one_or_none()
                if camp:
                    set_r = await db.execute(
                        select(Setting).where(
                            Setting.user_id == camp.user_id,
                            Setting.key.in_(["ssl_auto_enabled", "visitor_capture_enabled"]),
                        )
                    )
                    settings_map = {s.key: s for s in set_r.scalars().all()}
                    ssl_s = settings_map.get("ssl_auto_enabled")
                    if ssl_s and str(ssl_s.value or "").lower() == "true":
                        run_certbot_ssl(srv, dom.domain, srv.path or "/var/www/html")
                    vis_s = settings_map.get("visitor_capture_enabled")
                    if vis_s and str(vis_s.value or "").lower() == "true":
                        deploy_sw_push(srv, srv.path or "/var/www/html")
            dw.status = "deployed"
            dw.deployed_at = datetime.utcnow()
            await db.commit()
            if getattr(srv, "auth_type", None) != "ftp":
                try:
                    from app.services.indexing import generate_sitemap_xml, generate_robots_txt
                    sitemap_xml = await generate_sitemap_xml(db, dom.id)
                    if sitemap_xml:
                        robots_txt = generate_robots_txt(dom.domain)
                        deploy_sitemap_robots_sync(
                            srv.host, srv.port or 22, srv.user,
                            srv.auth_type or "password", srv.auth_data or "",
                            srv.path or "/var/www/html",
                            sitemap_xml, robots_txt,
                        )
                except Exception:
                    pass
                try:
                    import secrets
                    from app.services.deploy import deploy_indexnow_key_sync
                    from app.services.indexing_submit import submit_to_indexnow
                    key_r = await db.execute(
                        select(Setting).where(
                            Setting.user_id == camp.user_id,
                            Setting.key == "indexnow_key",
                        )
                    )
                    key_row = key_r.scalar_one_or_none()
                    indexnow_key = (key_row.value or "").strip() if key_row else ""
                    if not indexnow_key or len(indexnow_key) < 8:
                        indexnow_key = secrets.token_hex(16)
                        if key_row:
                            key_row.value = indexnow_key
                        else:
                            db.add(Setting(user_id=camp.user_id, key="indexnow_key", value=indexnow_key))
                        await db.commit()
                    deploy_indexnow_key_sync(
                        srv.host, srv.port or 22, srv.user,
                        srv.auth_type or "password", srv.auth_data or "",
                        srv.path or "/var/www/html", indexnow_key,
                    )
                    url = await get_doorway_url(db, doorway_id)
                    if url:
                        domain_origin = "https://" + (dom.domain or "").replace("https://", "").replace("http://", "").strip().rstrip("/")
                        await submit_to_indexnow(url, indexnow_key, f"{domain_origin}/{indexnow_key}.txt")
                except Exception:
                    pass
            return {"status": "ok", "message": msg}

    try:
        return asyncio.run(run())
    except Exception as e:
        return {"status": "error", "message": str(e)}


@celery_app.task(bind=True)
def deploy_batch_with_stagger(
    self,
    doorway_ids: list[int],
    min_delay_sec: float = 30,
    max_delay_sec: float = 180,
):
    """
    Deploy multiple doorways with staggered delays (anti-detection).
    Progress/pause/cancel stored in Redis under deploy_batch:{task_id}.
    """
    from app.services.anti_detection import StaggerConfig, sleep_for_stagger
    from app.services.batch_deploy_state import get_state, set_state, update_state
    import time

    task_id = self.request.id
    cfg = StaggerConfig(min_delay_sec=min_delay_sec, max_delay_sec=max_delay_sec)
    total = len(doorway_ids)
    results = [{"doorway_id": dw_id, "status": "pending", "message": None} for dw_id in doorway_ids]
    existing = get_state(task_id) or {}
    existing.update({
        "status": "running",
        "doorway_ids": doorway_ids,
        "current_index": 0,
        "results": results,
        "total": total,
        "error": None,
    })
    set_state(task_id, existing)

    def check_pause_cancel() -> bool:
        """Return True to break (cancelled), False to continue."""
        s = get_state(task_id)
        if not s:
            return False
        if s.get("status") == "cancelled":
            return True
        while s.get("status") == "paused":
            time.sleep(1)
            s = get_state(task_id)
            if s and s.get("status") == "cancelled":
                return True
        return False

    def check_pause_cancel() -> bool:
        """Return True to break (cancelled), False to continue."""
        s = get_state(task_id)
        if not s:
            return False
        if s.get("status") == "cancelled":
            return True
        while s.get("status") == "paused":
            time.sleep(1)
            s = get_state(task_id)
            if s and s.get("status") == "cancelled":
                return True
        return False

    results_out: list = []

    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from app.core.config import settings
    from app.models.doorway import Doorway
    from app.models.domain import Domain
    from app.models.server import Server
    from app.models.campaign import Campaign
    from app.models.setting import Setting
    from app.services.deploy import deploy_doorway_sync, prepare_doorway_html, run_certbot_ssl, deploy_sw_push, deploy_sitemap_robots_sync, deploy_indexnow_key_sync
    from app.services.indexing import get_doorway_url, generate_sitemap_xml, generate_robots_txt
    from datetime import datetime

    async def run():
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            for i, dw_id in enumerate(doorway_ids):
                if check_pause_cancel():
                    break
                update_state(task_id, current_index=i, results=[{"doorway_id": x["doorway_id"], "status": x["status"], "message": x.get("message")} for x in results])
                results[i]["status"] = "deploying"
                update_state(task_id, results=[{"doorway_id": x["doorway_id"], "status": x["status"], "message": x.get("message")} for x in results])
                sleep_for_stagger(i, total, cfg)
                if check_pause_cancel():
                    break
                html = await prepare_doorway_html(db, dw_id, for_bot=False)
                if not html:
                    results[i]["status"] = "error"
                    results[i]["message"] = "Could not prepare HTML"
                    results_out.append({"doorway_id": dw_id, "ok": False, "msg": "Could not prepare HTML"})
                    update_state(task_id, results=[{"doorway_id": x["doorway_id"], "status": x["status"], "message": x.get("message")} for x in results])
                    continue
                r = await db.execute(
                    select(Doorway, Domain, Server, Campaign)
                    .join(Domain, Doorway.domain_id == Domain.id)
                    .join(Server, Domain.server_id == Server.id)
                    .join(Campaign, Doorway.campaign_id == Campaign.id)
                    .where(Doorway.id == dw_id)
                )
                row = r.first()
                if not row:
                    results[i]["status"] = "error"
                    results[i]["message"] = "Not found"
                    results_out.append({"doorway_id": dw_id, "ok": False, "msg": "Not found"})
                    update_state(task_id, results=[{"doorway_id": r["doorway_id"], "status": r["status"], "message": r.get("message")} for r in results])
                    continue
                dw, dom, srv, camp = row
                ok, msg = deploy_doorway_sync(srv, dom.domain, dw.path or "/", html, srv.path)
                if not ok:
                    results[i]["status"] = "error"
                    results[i]["message"] = msg
                    results_out.append({"doorway_id": dw_id, "ok": False, "msg": msg})
                    update_state(task_id, results=[{"doorway_id": r["doorway_id"], "status": r["status"], "message": r.get("message")} for r in results])
                    continue
                camp_cloaking = (camp.affiliate_rules or {}).get("cloaking") or {}
                dw_cloaking = (dw.cloaking_rules or {}).get("cloaking") or {}
                cloaking_enabled = (isinstance(camp_cloaking, dict) and camp_cloaking.get("enabled")) or (isinstance(dw_cloaking, dict) and dw_cloaking.get("enabled")) or bool((dw.cloaking_rules or {}).get("cloaking_enabled"))
                if ok and cloaking_enabled:
                    html_seo = await prepare_doorway_html(db, dw_id, for_bot=True)
                    if html_seo:
                        deploy_doorway_sync(srv, dom.domain, dw.path or "/", html_seo, srv.path, remote_suffix=".seo")
                if getattr(srv, "auth_type", None) != "ftp":
                    if camp:
                        set_r = await db.execute(
                            select(Setting).where(
                                Setting.user_id == camp.user_id,
                                Setting.key.in_(["ssl_auto_enabled", "visitor_capture_enabled"]),
                            )
                        )
                        settings_map = {s.key: s for s in set_r.scalars().all()}
                        ssl_s = settings_map.get("ssl_auto_enabled")
                        if ssl_s and str(ssl_s.value or "").lower() == "true":
                            run_certbot_ssl(srv, dom.domain, srv.path or "/var/www/html")
                        vis_s = settings_map.get("visitor_capture_enabled")
                        if vis_s and str(vis_s.value or "").lower() == "true":
                            deploy_sw_push(srv, srv.path or "/var/www/html")
                dw.status = "deployed"
                dw.deployed_at = datetime.utcnow()
                if getattr(srv, "auth_type", None) != "ftp":
                    try:
                        sitemap_xml = await generate_sitemap_xml(db, dom.id)
                        if sitemap_xml:
                            robots_txt = generate_robots_txt(dom.domain)
                            deploy_sitemap_robots_sync(
                                srv.host, srv.port or 22, srv.user,
                                srv.auth_type or "password", srv.auth_data or "",
                                srv.path or "/var/www/html",
                                sitemap_xml, robots_txt,
                            )
                    except Exception:
                        pass
                    try:
                        import secrets
                        from app.services.indexing_submit import submit_to_indexnow
                        key_r = await db.execute(
                            select(Setting).where(
                                Setting.user_id == camp.user_id,
                                Setting.key == "indexnow_key",
                            )
                        )
                        key_row = key_r.scalar_one_or_none()
                        indexnow_key = (key_row.value or "").strip() if key_row else ""
                        if not indexnow_key or len(indexnow_key) < 8:
                            indexnow_key = secrets.token_hex(16)
                            if key_row:
                                key_row.value = indexnow_key
                            else:
                                db.add(Setting(user_id=camp.user_id, key="indexnow_key", value=indexnow_key))
                            await db.commit()
                        deploy_indexnow_key_sync(
                            srv.host, srv.port or 22, srv.user,
                            srv.auth_type or "password", srv.auth_data or "",
                            srv.path or "/var/www/html", indexnow_key,
                        )
                        url_in = await get_doorway_url(db, dw_id)
                        if url_in:
                            domain_origin = "https://" + (dom.domain or "").replace("https://", "").replace("http://", "").strip().rstrip("/")
                            await submit_to_indexnow(url_in, indexnow_key, f"{domain_origin}/{indexnow_key}.txt")
                    except Exception:
                        pass
                results[i]["status"] = "success"
                results[i]["message"] = msg
                results_out.append({"doorway_id": dw_id, "ok": True, "msg": msg})
                update_state(task_id, results=[{"doorway_id": x["doorway_id"], "status": x["status"], "message": x.get("message")} for x in results])
                url = await get_doorway_url(db, dw_id)
                if url and camp:
                    cred_r = await db.execute(
                        select(Setting).where(
                            Setting.user_id == camp.user_id,
                            Setting.key.in_([
                                "gsc_client_id", "gsc_client_secret", "gsc_refresh_token",
                                "bing_api_key",
                            ]),
                        )
                    )
                    creds = {s.key: (s.value or "").strip() for s in cred_r.scalars().all()}
                    if creds.get("gsc_client_id") or creds.get("bing_api_key"):
                        from app.services.indexing_submit import submit_to_gsc, submit_to_bing
                        from app.services.gsc_ratelimit import check_gsc_limit, record_gsc_submission
                        if creds.get("gsc_client_id") and creds.get("gsc_client_secret") and creds.get("gsc_refresh_token"):
                            allowed, _ = check_gsc_limit(camp.user_id)
                            if allowed:
                                gsc_ok, _ = await submit_to_gsc(
                                    url, creds["gsc_client_id"], creds["gsc_client_secret"], creds["gsc_refresh_token"],
                                )
                                if gsc_ok:
                                    record_gsc_submission(camp.user_id)
                        if creds.get("bing_api_key"):
                            await submit_to_bing(url, creds["bing_api_key"])
            await db.commit()
        final_status = "cancelled" if get_state(task_id) and get_state(task_id).get("status") == "cancelled" else "completed"
        update_state(task_id, status=final_status, results=[{"doorway_id": x["doorway_id"], "status": x["status"], "message": x.get("message")} for x in results])
        return {"status": "ok", "results": results_out}

    try:
        out = asyncio.run(run())
        return out
    except Exception as e:
        update_state(task_id, status="completed", error=str(e))
        return {"status": "error", "message": str(e), "results": results_out}


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
