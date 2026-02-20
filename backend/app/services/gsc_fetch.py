"""Fetch impressions/clicks from Google Search Console Search Analytics API."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doorway import Doorway, DoorwayMetrics
from app.models.domain import Domain
from app.models.campaign import Campaign


async def get_gsc_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> Optional[str]:
    """Get OAuth2 access token for GSC API."""
    if not all([client_id, client_secret, refresh_token]):
        return None
    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        def _refresh():
            creds.refresh(Request())
            return creds.token
        return await asyncio.to_thread(_refresh)
    except (RefreshError, Exception):
        return None


async def fetch_gsc_searchanalytics(
    site_url: str,
    start_date: str,
    end_date: str,
    access_token: str,
) -> list[dict]:
    """
    Fetch Search Analytics data by page URL.
    site_url: GSC property, e.g. "sc-domain:example.com" or "https://example.com/"
    Returns list of {page, impressions, clicks, ctr, position}.
    """
    encoded_site = quote(site_url, safe="")
    api_url = f"https://www.googleapis.com/webmasters/v3/sites/{encoded_site}/searchAnalytics/query"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["page", "date"],
        "rowLimit": 25000,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(api_url, json=payload, headers=headers)
            if r.status_code != 200:
                return []
            data = r.json()
    except Exception:
        return []
    rows = data.get("rows") or []
    result = []
    for r in rows:
        keys = r.get("keys") or []
        page = keys[0] if keys else ""
        date_str = keys[1] if len(keys) > 1 else end_date
        result.append({
            "page": page,
            "date": date_str,
            "impressions": r.get("impressions", 0),
            "clicks": r.get("clicks", 0),
            "ctr": r.get("ctr", 0),
            "position": r.get("position", 0),
        })
    return result


async def import_gsc_to_doorway_metrics(
    db: AsyncSession,
    user_id: int,
    domain_id: int,
    site_url: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    days: int = 28,
) -> dict:
    """
    Fetch GSC data for domain's doorways and upsert into DoorwayMetrics.
    site_url: GSC property (sc-domain:example.com or https://example.com/)
    Returns {imported: N, errors: [...]}.
    """
    token = await get_gsc_access_token(client_id, client_secret, refresh_token)
    if not token:
        return {"imported": 0, "errors": ["GSC auth failed"]}

    end = datetime.utcnow().date()
    start = end - timedelta(days=days)
    start_str = start.isoformat()
    end_str = end.isoformat()

    rows = await fetch_gsc_searchanalytics(site_url, start_str, end_str, token)
    if not rows:
        return {"imported": 0, "errors": []}

    # Get domain and doorways
    r = await db.execute(
        select(Domain, Doorway)
        .join(Doorway, Doorway.domain_id == Domain.id)
        .join(Campaign, Doorway.campaign_id == Campaign.id)
        .where(Domain.id == domain_id, Campaign.user_id == user_id)
    )
    url_to_doorway: dict[str, Doorway] = {}
    for dom, dw in r.all():
        base = f"https://{dom.domain}".rstrip("/")
        path = (dw.path or "/").strip()
        full_url = base if path == "/" else f"{base}{path}"
        url_to_doorway[full_url] = dw
        url_to_doorway[full_url.rstrip("/")] = dw

    imported = 0
    for row in rows:
        page = (row.get("page") or "").rstrip("/")
        if not page:
            continue
        dw = url_to_doorway.get(page) or url_to_doorway.get(page + "/")
        if not dw:
            continue
        imp = int(row.get("impressions") or 0)
        clk = int(row.get("clicks") or 0)
        if imp == 0 and clk == 0:
            continue
        date_str = row.get("date") or end_str
        try:
            day_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            day_date = end
        day_start = datetime.combine(day_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        r2 = await db.execute(
            select(DoorwayMetrics).where(
                DoorwayMetrics.doorway_id == dw.id,
                DoorwayMetrics.date >= day_start,
                DoorwayMetrics.date < day_end,
            )
        )
        m = r2.scalar_one_or_none()
        ctr = float(row.get("ctr") or 0)
        pos = float(row.get("position") or 0)
        if m:
            m.impressions = (m.impressions or 0) + imp
            m.clicks = (m.clicks or 0) + clk
            m.ctr = ctr if ctr else (m.clicks / m.impressions * 100 if m.impressions else 0)
            m.avg_position = pos if pos else m.avg_position
        else:
            m = DoorwayMetrics(
                doorway_id=dw.id,
                date=day_start,
                impressions=imp,
                clicks=clk,
                ctr=ctr or (clk / imp * 100 if imp else 0),
                avg_position=pos,
            )
            db.add(m)
        imported += 1
    await db.commit()
    return {"imported": imported, "errors": []}
