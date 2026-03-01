"""Deploy API."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.doorway import Doorway
from app.models.campaign import Campaign
from app.models.domain import Domain
from app.models.setting import Setting
from app.models.server import Server
from app.services.deploy import prepare_doorway_html, deploy_doorway_sync, deploy_doorway_ftp, deploy_sw_push, run_certbot_ssl, deploy_sitemap_robots_sync, deploy_indexnow_key_sync
from app.services.indexing import get_doorway_url, generate_sitemap_xml, generate_robots_txt

router = APIRouter()


async def _submit_to_indexing_after_deploy(url: str, user_id: int, creds: dict) -> None:
    """Фоновая отправка URL в GSC и Bing после деплоя."""
    from app.services.indexing_submit import submit_to_gsc, submit_to_bing
    from app.services.gsc_ratelimit import check_gsc_limit, record_gsc_submission
    if creds.get("gsc_client_id") and creds.get("gsc_client_secret") and creds.get("gsc_refresh_token"):
        allowed, _ = check_gsc_limit(user_id)
        if allowed:
            gsc_ok, _ = await submit_to_gsc(
                url,
                creds["gsc_client_id"],
                creds["gsc_client_secret"],
                creds["gsc_refresh_token"],
            )
            if gsc_ok:
                record_gsc_submission(user_id)
    if creds.get("bing_api_key"):
        await submit_to_bing(url, creds["bing_api_key"])


async def _submit_indexnow_after_deploy(url: str, key: str, key_location: str) -> None:
    """Фоновая отправка URL в IndexNow после деплоя."""
    from app.services.indexing_submit import submit_to_indexnow
    await submit_to_indexnow(url, key, key_location)


class BatchDeployRequest(BaseModel):
    doorway_ids: list[int]
    min_delay_sec: float = 30
    max_delay_sec: float = 180


@router.post("/doorway/{doorway_id}")
async def deploy_doorway(
    doorway_id: int,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Doorway, Campaign)
        .join(Campaign, Doorway.campaign_id == Campaign.id)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    row = r.first()
    if not row:
        raise HTTPException(status_code=404, detail="Doorway not found")
    dw, camp = row
    html = await prepare_doorway_html(db, doorway_id, for_bot=False)
    if not html:
        raise HTTPException(status_code=500, detail="Could not prepare HTML")
    camp_cloaking = (camp.affiliate_rules or {}).get("cloaking") or {}
    dw_cloaking = (dw.cloaking_rules or {}).get("cloaking") or {}
    cloaking_enabled = (isinstance(camp_cloaking, dict) and camp_cloaking.get("enabled")) or (isinstance(dw_cloaking, dict) and dw_cloaking.get("enabled")) or bool((dw.cloaking_rules or {}).get("cloaking_enabled"))
    r2 = await db.execute(
        select(Domain, Server)
        .join(Server, Domain.server_id == Server.id)
        .where(Domain.id == dw.domain_id)
    )
    row = r2.first()
    if not row:
        raise HTTPException(status_code=404, detail="Domain or server not found")
    dom, srv = row
    if getattr(srv, "auth_type", None) == "ftp":
        ok, msg = deploy_doorway_ftp(
            host=srv.host,
            user=srv.user,
            password=srv.auth_data or "",
            path=dw.path or "/",
            html_content=html,
            remote_path=srv.path or "/",
            port=srv.port or 21,
        )
    else:
        ok, msg = deploy_doorway_sync(
            server=srv,
            domain=dom.domain,
            path=dw.path or "/",
            html_content=html,
            base_path=srv.path,
        )
        if ok and cloaking_enabled:
            html_seo = await prepare_doorway_html(db, doorway_id, for_bot=True)
            if html_seo:
                ok2, msg2 = deploy_doorway_sync(
                    server=srv,
                    domain=dom.domain,
                    path=dw.path or "/",
                    html_content=html_seo,
                    base_path=srv.path,
                    remote_suffix=".seo",
                )
                if ok2:
                    msg += "; cloaking SEO version deployed (index.seo.html)"
    if not ok:
        raise HTTPException(status_code=500, detail=f"Deploy failed: {msg}")
    # Deploy service worker for push (when visitor capture may be used)
    if getattr(srv, "auth_type", None) != "ftp":
        set_vis = await db.execute(
            select(Setting).where(
                Setting.user_id == current_user.id,
                Setting.key == "visitor_capture_enabled",
            )
        )
        vis_row = set_vis.scalar_one_or_none()
        if vis_row and str(vis_row.value or "").lower() == "true":
            deploy_sw_push(srv, srv.path or "/var/www/html")
    # SSL auto (Let's Encrypt) — only for SSH deploy
    if getattr(srv, "auth_type", None) != "ftp":
        set_r = await db.execute(
            select(Setting).where(
                Setting.user_id == current_user.id,
                Setting.key == "ssl_auto_enabled",
            )
        )
        ssl_row = set_r.scalar_one_or_none()
        if ssl_row and str(ssl_row.value).lower() == "true":
            ssl_ok, ssl_msg = run_certbot_ssl(
                server=srv,
                domain=dom.domain,
                webroot=srv.path or "/var/www/html",
            )
            if ssl_ok:
                msg += "; SSL certificate issued"
            elif "certificate" in ssl_msg.lower():
                msg += "; " + ssl_msg[:200]
    from datetime import datetime
    dw.status = "deployed"
    dw.deployed_at = datetime.utcnow()
    dw.pause_reason = None
    await db.commit()
    try:
        from app.services.webhook_service import notify_webhooks
        await notify_webhooks(db, current_user.id, "doorway.deployed", {
            "doorway_id": doorway_id, "domain": dom.domain, "path": dw.path or "/",
        })
    except Exception:
        pass
    url = await get_doorway_url(db, doorway_id)
    # Sitemap + robots.txt on server (SSH only, automatic)
    if getattr(srv, "auth_type", None) != "ftp":
        import asyncio
        sitemap_xml = await generate_sitemap_xml(db, dom.id)
        if sitemap_xml:
            robots_txt = generate_robots_txt(dom.domain)
            try:
                ok_sr, msg_sr = await asyncio.to_thread(
                    deploy_sitemap_robots_sync,
                    srv.host,
                    srv.port or 22,
                    srv.user,
                    srv.auth_type or "password",
                    srv.auth_data or "",
                    srv.path or "/var/www/html",
                    sitemap_xml,
                    robots_txt,
                )
                if ok_sr:
                    msg += "; sitemap+robots deployed"
                else:
                    msg += "; sitemap/robots: " + (msg_sr[:80] if msg_sr else "failed")
            except Exception as e:
                msg += "; sitemap/robots: " + str(e)[:80]
    # IndexNow: upload key file and submit URL (SSH only)
    if getattr(srv, "auth_type", None) != "ftp" and url:
        import secrets
        key_r = await db.execute(
            select(Setting).where(
                Setting.user_id == current_user.id,
                Setting.key == "indexnow_key",
            )
        )
        key_row = key_r.scalar_one_or_none()
        indexnow_key = (key_row.value or "").strip() if key_row else ""
        if not indexnow_key or len(indexnow_key) < 8:
            indexnow_key = secrets.token_hex(16)
            if key_row:
                key_row.value = indexnow_key
                key_row.updated_at = datetime.utcnow()
            else:
                db.add(Setting(user_id=current_user.id, key="indexnow_key", value=indexnow_key))
            await db.commit()
        try:
            await asyncio.to_thread(
                deploy_indexnow_key_sync,
                srv.host, srv.port or 22, srv.user,
                srv.auth_type or "password", srv.auth_data or "",
                srv.path or "/var/www/html",
                indexnow_key,
            )
            domain_origin = "https://" + (dom.domain or "").replace("https://", "").replace("http://", "").strip().rstrip("/")
            key_location = f"{domain_origin}/{indexnow_key}.txt"
            background_tasks.add_task(
                _submit_indexnow_after_deploy,
                url, indexnow_key, key_location,
            )
        except Exception:
            pass
    if url:
        cred_r = await db.execute(
            select(Setting).where(
                Setting.user_id == current_user.id,
                Setting.key.in_([
                    "gsc_client_id", "gsc_client_secret", "gsc_refresh_token",
                    "bing_api_key",
                ]),
            )
        )
        creds = {s.key: (s.value or "").strip() for s in cred_r.scalars().all()}
        if creds.get("gsc_client_id") or creds.get("bing_api_key"):
            background_tasks.add_task(_submit_to_indexing_after_deploy, url, current_user.id, creds)
    return {"status": "ok", "message": msg}


@router.post("/batch")
async def deploy_batch(
    body: BatchDeployRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Deploy multiple doorways with staggered delays (anti-detection).
    Runs in Celery background. Returns task_id to poll status.
    """
    from app.tasks.doorway_tasks import deploy_batch_with_stagger

    if not body.doorway_ids:
        raise HTTPException(status_code=400, detail="doorway_ids required")
    if len(body.doorway_ids) > 50:
        raise HTTPException(status_code=400, detail="Max 50 doorways per batch")
    r = await db.execute(
        select(Doorway.id)
        .join(Campaign)
        .where(Doorway.id.in_(body.doorway_ids), Campaign.user_id == current_user.id)
    )
    allowed = {row[0] for row in r.all()}
    ids = [i for i in body.doorway_ids if i in allowed]
    if not ids:
        raise HTTPException(status_code=404, detail="No doorways found")
    task = deploy_batch_with_stagger.delay(
        ids,
        min_delay_sec=body.min_delay_sec,
        max_delay_sec=body.max_delay_sec,
    )
    return {"status": "queued", "task_id": task.id, "doorway_ids": ids}
