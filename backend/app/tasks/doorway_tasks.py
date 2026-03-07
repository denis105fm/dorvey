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
            cloaking = {}
            from sqlalchemy import select
            from app.models.campaign import Campaign
            camp = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
            if camp and getattr(camp, "is_black", False) and result.get("seo_tail"):
                cloaking["seo_tail"] = (result.get("seo_tail") or "").strip()[:500]
            dw = Doorway(
                campaign_id=campaign_id, domain_id=domain_id, path=path,
                title=result.get("title"), content=result.get("content"),
                meta_description=result.get("meta_description"), status="draft",
                cloaking_rules=cloaking if cloaking else None,
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
    from app.services.batch_deploy_state import get_state, set_state, update_state, remove_user_task
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
                sleep_for_stagger(i, total, stagger_cfg)
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
                await db.commit()
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
        user_id = (get_state(task_id) or {}).get("user_id")
        if user_id is not None:
            remove_user_task(user_id, task_id)
        return {"status": "ok", "results": results_out}

    try:
        out = asyncio.run(run())
        return out
    except Exception as e:
        update_state(task_id, status="completed", error=str(e))
        user_id = (get_state(task_id) or {}).get("user_id")
        if user_id is not None:
            remove_user_task(user_id, task_id)
        return {"status": "error", "message": str(e), "results": results_out}


def _generate_batch_geos_for_item(item: dict, target_geos: list | None) -> list[str | None]:
    """Return list of geos for one batch item (same logic as API)."""
    geos: list[str | None] = []
    gs = target_geos or (item.get("target_geos") or [])
    if gs:
        geos = [str(g).strip().upper()[:2] if g else None for g in gs if (g or "").strip()]
    if not geos and (item.get("target_geo") or "").strip():
        geos = [(item.get("target_geo") or "").strip().upper()[:2]]
    if not geos:
        geos = [None]
    return geos


@celery_app.task(bind=True)
def generate_batch_async(
    self,
    user_id: int,
    items: list[dict],
    generate_faq: bool = False,
    generate_quiz: bool = False,
    target_geos: list[str] | None = None,
):
    """
    Run batch doorway generation in background.
    Progress stored in Redis under generate_batch:{task_id}.
    """
    import asyncio
    from app.services.generate_batch_state import get_state, set_state, update_state, remove_user_task
    from app.services.generator import generate_doorway, _keyword_to_slug
    from app.services.dataforseo_service import get_language_code
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from app.core.config import settings
    from app.models.doorway import Doorway, DoorwayVersion
    from app.models.campaign import Campaign

    task_id = self.request.id
    max_created = 100
    items = (items or [])[:50]
    results: list[dict] = []
    created = 0

    async def _check_campaign(db: AsyncSession, campaign_id: int, uid: int) -> bool:
        r = await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == uid))
        return r.scalar_one_or_none() is not None

    async def run():
        nonlocal created, results
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        total_estimate = 0
        for it in items:
            if total_estimate >= max_created:
                break
            gs = _generate_batch_geos_for_item(it, target_geos)
            total_estimate += len(gs)
        total_estimate = min(total_estimate, max_created)
        async with async_session() as db:
            set_state(task_id, {
                "user_id": user_id,
                "status": "running",
                "total": total_estimate,
                "current_index": 0,
                "results": [],
                "created": 0,
                "error": None,
            })
            for item in items:
                if created >= max_created:
                    break
                ok = await _check_campaign(db, item.get("campaign_id") or 0, user_id)
                if not ok:
                    results.append({"keyword": item.get("keyword", ""), "geo": "-", "status": "error", "error": "Campaign not found"})
                    update_state(task_id, current_index=len(results), results=results, created=created)
                    continue
                geos = _generate_batch_geos_for_item(item, target_geos)
                base_path = (item.get("path") or "/").strip() or "/"
                slug = _keyword_to_slug(item.get("keyword", "")) if base_path == "/" else (base_path.strip("/").split("/")[0] or _keyword_to_slug(item.get("keyword", "")))
                for geo in geos:
                    if created >= max_created:
                        break
                    if len(geos) > 1 and geo:
                        path_use = f"/{get_language_code(geo)}/{slug}"
                    else:
                        path_use = base_path if base_path != "/" else f"/{slug}"
                    try:
                        gen_result = await generate_doorway(
                            db,
                            campaign_id=item["campaign_id"],
                            domain_id=item["domain_id"],
                            keyword=item["keyword"],
                            path=path_use,
                            generate_faq=generate_faq,
                            generate_quiz=generate_quiz,
                            target_geo=geo,
                        )
                    except (ValueError, Exception) as e:
                        results.append({"keyword": item.get("keyword", ""), "geo": geo or "-", "status": "error", "error": str(e)[:200]})
                        update_state(task_id, current_index=len(results), results=results, created=created)
                        continue
                    try:
                        cloaking = {}
                        if gen_result.get("faq_qa"):
                            cloaking["faq_qa"] = gen_result["faq_qa"]
                        if gen_result.get("quiz_questions"):
                            cloaking["quiz"] = {"enabled": True, "questions": gen_result["quiz_questions"]}
                        camp = (await db.execute(select(Campaign).where(Campaign.id == item["campaign_id"]))).scalar_one_or_none()
                        if camp and getattr(camp, "is_black", False) and gen_result.get("seo_tail"):
                            cloaking["seo_tail"] = (gen_result.get("seo_tail") or "").strip()[:500]
                        preferred_layout = None
                        if camp and camp.affiliate_rules and isinstance(camp.affiliate_rules.get("ai"), dict):
                            preferred_layout = camp.affiliate_rules["ai"].get("preferred_layout_index")
                        dw = Doorway(
                            campaign_id=item["campaign_id"],
                            domain_id=item["domain_id"],
                            path=path_use,
                            title=gen_result.get("title"),
                            content=gen_result.get("content"),
                            meta_description=gen_result.get("meta_description"),
                            status="draft",
                            cloaking_rules=cloaking if cloaking else None,
                            layout_index=preferred_layout if preferred_layout is not None else None,
                            target_geo=geo,
                        )
                        db.add(dw)
                        await db.flush()
                        created += 1
                        ver = DoorwayVersion(doorway_id=dw.id, content_snapshot={
                            "title": dw.title, "content": dw.content, "meta_description": dw.meta_description,
                        })
                        db.add(ver)
                        results.append({"keyword": item.get("keyword", ""), "geo": geo or "-", "status": "ok", "doorway_id": dw.id})
                    except Exception as ex:
                        results.append({"keyword": item.get("keyword", ""), "geo": geo or "-", "status": "error", "error": str(ex)})
                    update_state(task_id, current_index=len(results), results=results, created=created)
            await db.commit()
            if created > 0:
                try:
                    from app.api.billing import notify_billing_limits_if_needed
                    await notify_billing_limits_if_needed(db, user_id)
                except Exception:
                    pass
        update_state(task_id, status="completed", results=results, created=created)

    try:
        asyncio.run(run())
        remove_user_task(user_id, task_id)
        return {"status": "ok", "created": created, "results": results}
    except Exception as e:
        update_state(task_id, status="completed", error=str(e), results=results, created=created)
        remove_user_task(user_id, task_id)
        return {"status": "error", "message": str(e), "created": created, "results": results}


@celery_app.task(bind=True)
def delete_batch_async(self, user_id: int, doorway_ids: list[int]):
    """
    Run batch doorway delete in background: remove from server then delete from DB.
    Progress stored in Redis under delete_batch:{task_id}.
    """
    import asyncio
    from app.services.delete_batch_state import set_state, update_state, remove_user_task
    from app.services.deploy import remove_doorway_from_server
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select, delete
    from app.core.config import settings
    from app.models.doorway import Doorway, DoorwayVersion, DoorwayMetrics
    from app.models.domain import Domain
    from app.models.server import Server
    from app.models.campaign import Campaign
    from app.models.doorway_source_metrics import DoorwaySourceMetrics
    from app.models.ab_variant import DoorwayABVariant

    task_id = self.request.id
    ids = list(doorway_ids or [])[:100]

    async def run():
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            r = await db.execute(
                select(Doorway.id, Doorway.path, Domain.domain, Server)
                .join(Campaign, Doorway.campaign_id == Campaign.id)
                .join(Domain, Doorway.domain_id == Domain.id)
                .join(Server, Domain.server_id == Server.id)
                .where(Doorway.id.in_(ids), Campaign.user_id == user_id)
            )
            rows = r.all()
            # Build list (id, path, domain, server) for allowed doorways only
            items = []
            for row in rows:
                dw_id, path, domain, server = row
                items.append({"doorway_id": dw_id, "path": path or "/", "domain": (domain or "").strip(), "server": server})
            allowed_ids = [x["doorway_id"] for x in items]
            if not allowed_ids:
                set_state(task_id, {"user_id": user_id, "status": "completed", "total": 0, "current_index": 0, "results": [], "deleted": 0})
                return
            results = [{"doorway_id": x["doorway_id"], "path": x["path"], "domain": x["domain"], "status": "pending"} for x in items]
            set_state(task_id, {
                "user_id": user_id,
                "status": "running",
                "total": len(results),
                "current_index": 0,
                "results": results,
                "deleted": 0,
            })
            for i, x in enumerate(items):
                ok, msg = remove_doorway_from_server(
                    server=x["server"],
                    path=x["path"],
                    base_path=x["server"].path or "/var/www/html",
                )
                results[i]["status"] = "removed" if ok else "error"
                results[i]["message"] = msg if not ok else None
                update_state(task_id, current_index=i + 1, results=results)
            await db.execute(delete(DoorwayVersion).where(DoorwayVersion.doorway_id.in_(allowed_ids)))
            await db.execute(delete(DoorwayMetrics).where(DoorwayMetrics.doorway_id.in_(allowed_ids)))
            await db.execute(delete(DoorwaySourceMetrics).where(DoorwaySourceMetrics.doorway_id.in_(allowed_ids)))
            await db.execute(delete(DoorwayABVariant).where(DoorwayABVariant.doorway_id.in_(allowed_ids)))
            await db.execute(delete(Doorway).where(Doorway.id.in_(allowed_ids)))
            await db.commit()
            update_state(task_id, status="completed", results=results, deleted=len(allowed_ids))

    try:
        asyncio.run(run())
        remove_user_task(user_id, task_id)
    except Exception as e:
        update_state(task_id, status="completed", error=str(e))
        remove_user_task(user_id, task_id)


@celery_app.task
def collect_server_metrics():
    """Collect metrics for all servers via SSH. Run periodically via Celery Beat."""
    import asyncio
    from datetime import datetime
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings
    from app.models.server import Server
    from app.models.server_metric import ServerMetric
    from app.services.server_metrics import collect_metrics_from_params

    async def run():
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            r = await db.execute(select(Server))
            servers = r.scalars().all()
            for srv in servers:
                try:
                    data = collect_metrics_from_params(
                        host=srv.host,
                        port=int(srv.port or 22),
                        user=srv.user or "root",
                        auth_type=srv.auth_type or "ssh_key",
                        auth_data=srv.auth_data,
                    )
                    if data:
                        m = ServerMetric(
                            server_id=srv.id,
                            created_at=datetime.utcnow(),
                            load_1=data.get("load_1"),
                            load_5=data.get("load_5"),
                            load_15=data.get("load_15"),
                            mem_total_kb=data.get("mem_total_kb"),
                            mem_available_kb=data.get("mem_available_kb"),
                            disk_total_kb=data.get("disk_total_kb"),
                            disk_used_kb=data.get("disk_used_kb"),
                            nproc=data.get("nproc"),
                        )
                        db.add(m)
                except Exception:
                    continue
            await db.commit()
        return {"status": "ok", "servers": len(servers)}

    try:
        return asyncio.run(run())
    except Exception as e:
        return {"status": "error", "message": str(e)}


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
                            cloaking = {}
                            camp = (await db.execute(select(Campaign).where(Campaign.id == camp_id))).scalar_one_or_none()
                            if camp and getattr(camp, "is_black", False) and result.get("seo_tail"):
                                cloaking["seo_tail"] = (result.get("seo_tail") or "").strip()[:500]
                            dw = Doorway(
                                campaign_id=camp_id, domain_id=domain_id, path=path,
                                title=result.get("title"), content=result.get("content"),
                                meta_description=result.get("meta_description"), status="draft",
                                cloaking_rules=cloaking if cloaking else None,
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
