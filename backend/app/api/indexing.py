"""Indexing API: sitemap, GSC, Bing."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.doorway import Doorway
from app.models.campaign import Campaign
from app.models.domain import Domain
from app.models.setting import Setting

from app.services.indexing import generate_sitemap_xml, get_doorway_url
from app.services.indexing_submit import submit_to_gsc, submit_to_bing

router = APIRouter()


@router.get("/sitemap/{domain_id}", response_class=PlainTextResponse)
async def get_sitemap(
    domain_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Domain).where(Domain.id == domain_id))
    dom_check = r.scalar_one_or_none()
    if not dom_check:
        raise HTTPException(status_code=404, detail="Domain not found")
    r2 = await db.execute(
        select(Doorway).join(Campaign).where(
            Doorway.domain_id == domain_id, Campaign.user_id == current_user.id
        )
    )
    has_doorway = r2.first() is not None
    if not has_doorway and dom_check.campaign_id:
        camp_r = await db.execute(select(Campaign).where(
            Campaign.id == dom_check.campaign_id, Campaign.user_id == current_user.id
        ))
        if not camp_r.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Access denied")
    elif not has_doorway:
        raise HTTPException(status_code=404, detail="Access denied")
    xml = await generate_sitemap_xml(db, domain_id)
    if not xml:
        raise HTTPException(status_code=404, detail="No doorways to index")
    return PlainTextResponse(xml, media_type="application/xml")


@router.post("/submit/{doorway_id}")
async def submit_doorway(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Submit doorway URL to GSC and Bing for indexing."""
    r = await db.execute(
        select(Doorway)
        .join(Campaign)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    dw = r.scalar_one_or_none()
    if not dw:
        raise HTTPException(status_code=404, detail="Doorway not found")
    url = await get_doorway_url(db, doorway_id)
    if not url:
        raise HTTPException(status_code=500, detail="Could not build URL")

    # Load GSC/Bing credentials from user settings
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

    gsc_ok, gsc_msg = False, "GSC credentials not configured"
    bing_ok, bing_msg = False, "Bing API key not configured"

    from app.services.gsc_ratelimit import check_gsc_limit, record_gsc_submission
    allowed, remaining = check_gsc_limit(current_user.id)
    if not allowed and creds.get("gsc_client_id"):
        return {
            "status": "rate_limited",
            "url": url,
            "gsc": {"submitted": False, "message": "GSC rate limit: max 200/hour. Try later."},
            "bing": {"submitted": bing_ok, "message": bing_msg},
        }

    if creds.get("gsc_client_id") and creds.get("gsc_client_secret") and creds.get("gsc_refresh_token"):
        gsc_ok, gsc_msg = await submit_to_gsc(
            url,
            creds["gsc_client_id"],
            creds["gsc_client_secret"],
            creds["gsc_refresh_token"],
        )
        if gsc_ok:
            record_gsc_submission(current_user.id)

    if creds.get("bing_api_key"):
        bing_ok, bing_msg = await submit_to_bing(url, creds["bing_api_key"])

    return {
        "status": "ok",
        "url": url,
        "gsc": {"submitted": gsc_ok, "message": gsc_msg},
        "bing": {"submitted": bing_ok, "message": bing_msg},
    }
