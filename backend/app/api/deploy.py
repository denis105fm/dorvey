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
from app.services.deploy import prepare_doorway_html, deploy_doorway_sync, deploy_doorway_ftp, deploy_sw_push, run_certbot_ssl

router = APIRouter()


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
        select(Doorway)
        .join(Campaign)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    dw = r.scalar_one_or_none()
    if not dw:
        raise HTTPException(status_code=404, detail="Doorway not found")
    html = await prepare_doorway_html(db, doorway_id)
    if not html:
        raise HTTPException(status_code=500, detail="Could not prepare HTML")
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
    await db.commit()
    try:
        from app.services.webhook_service import notify_webhooks
        await notify_webhooks(db, current_user.id, "doorway.deployed", {
            "doorway_id": doorway_id, "domain": dom.domain, "path": dw.path or "/",
        })
    except Exception:
        pass
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
