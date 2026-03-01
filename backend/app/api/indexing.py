"""Indexing API: sitemap, GSC, Bing."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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


@router.post("/submit-domain/{domain_id}")
async def submit_domain(
    domain_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Submit all doorway URLs of the domain to GSC and Bing (respects GSC rate limit)."""
    from app.services.gsc_ratelimit import check_gsc_limit, record_gsc_submission

    r = await db.execute(
        select(Domain).where(Domain.id == domain_id)
    )
    dom = r.scalar_one_or_none()
    if not dom:
        raise HTTPException(status_code=404, detail="Domain not found")
    r2 = await db.execute(
        select(Doorway)
        .join(Campaign)
        .where(
            Doorway.domain_id == domain_id,
            Campaign.user_id == current_user.id,
            Doorway.status.in_(["deployed", "indexed", "draft"]),
        )
    )
    doorways = list(r2.scalars().all())
    if not doorways:
        return {
            "status": "ok",
            "domain": dom.domain,
            "sitemap_url": f"https://{dom.domain.replace('https://', '').replace('http://', '').strip().rstrip('/')}/sitemap.xml",
            "submitted": 0,
            "gsc_count": 0,
            "bing_count": 0,
            "rate_limited": False,
            "message": "No doorways to submit",
        }

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

    sitemap_url = f"https://{dom.domain.replace('https://', '').replace('http://', '').strip().rstrip('/')}/sitemap.xml"
    gsc_count = 0
    bing_count = 0
    submitted = 0

    for dw in doorways:
        url = await get_doorway_url(db, dw.id)
        if not url:
            continue
        if creds.get("gsc_client_id") and creds.get("gsc_client_secret") and creds.get("gsc_refresh_token"):
            allowed, _ = check_gsc_limit(current_user.id)
            if allowed:
                gsc_ok, _ = await submit_to_gsc(
                    url,
                    creds["gsc_client_id"],
                    creds["gsc_client_secret"],
                    creds["gsc_refresh_token"],
                )
                if gsc_ok:
                    record_gsc_submission(current_user.id)
                    gsc_count += 1
            else:
                break
        if creds.get("bing_api_key"):
            bing_ok, _ = await submit_to_bing(url, creds["bing_api_key"])
            if bing_ok:
                bing_count += 1
        submitted += 1

    return {
        "status": "ok",
        "domain": dom.domain,
        "sitemap_url": sitemap_url,
        "submitted": submitted,
        "total": len(doorways),
        "gsc_count": gsc_count,
        "bing_count": bing_count,
        "rate_limited": submitted < len(doorways) and bool(creds.get("gsc_client_id")),
        "message": f"Submitted {submitted}/{len(doorways)} URLs" + (" (GSC limit reached)" if submitted < len(doorways) else ""),
    }


class GscFetchRequest(BaseModel):
    domain_id: int
    site_url: str  # GSC property: sc-domain:example.com or https://example.com/
    days: int = 28


@router.post("/gsc-fetch")
async def fetch_gsc_data(
    data: GscFetchRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch impressions/clicks from GSC Search Analytics API and import into DoorwayMetrics.
    Requires GSC credentials in settings. site_url: GSC property (sc-domain:example.com or https://example.com/)
    """
    r = await db.execute(
        select(Domain).where(Domain.id == data.domain_id)
    )
    dom = r.scalar_one_or_none()
    if not dom:
        raise HTTPException(404, "Domain not found")
    r2 = await db.execute(
        select(Doorway).join(Campaign).where(
            Doorway.domain_id == data.domain_id,
            Campaign.user_id == current_user.id,
        )
    )
    if not r2.first():
        raise HTTPException(403, "Access denied to domain")
    cred_r = await db.execute(
        select(Setting).where(
            Setting.user_id == current_user.id,
            Setting.key.in_(["gsc_client_id", "gsc_client_secret", "gsc_refresh_token"]),
        )
    )
    creds = {s.key: (s.value or "").strip() for s in cred_r.scalars().all()}
    if not all(creds.get(k) for k in ["gsc_client_id", "gsc_client_secret", "gsc_refresh_token"]):
        raise HTTPException(400, "GSC credentials not configured in Settings")
    from app.services.gsc_fetch import import_gsc_to_doorway_metrics
    result = await import_gsc_to_doorway_metrics(
        db, current_user.id, data.domain_id, data.site_url,
        creds["gsc_client_id"], creds["gsc_client_secret"], creds["gsc_refresh_token"],
        days=min(data.days, 90),
    )
    return {"status": "ok", **result}
