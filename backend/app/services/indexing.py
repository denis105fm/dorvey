"""Indexing: sitemap generation."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.doorway import Doorway
from app.models.domain import Domain


async def generate_sitemap_xml(db: AsyncSession, domain_id: int) -> Optional[str]:
    """Generate sitemap.xml for domain's doorways."""
    r = await db.execute(
        select(Domain).where(Domain.id == domain_id)
    )
    dom = r.scalar_one_or_none()
    if not dom:
        return None
    r2 = await db.execute(
        select(Doorway).where(
            Doorway.domain_id == domain_id,
            Doorway.status.in_(["deployed", "indexed", "draft"])
        )
    )
    doorways = r2.scalars().all()
    base = f"https://{dom.domain}".rstrip("/")
    urls = []
    for dw in doorways:
        path = dw.path or "/"
        url = base if path == "/" else f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
        urls.append(f"  <url><loc>{url}</loc></url>")
    if not urls:
        urls = [f"  <url><loc>{base}</loc></url>"]
    body = "\n".join(urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>'


async def get_doorway_url(db: AsyncSession, doorway_id: int) -> Optional[str]:
    """Get full URL for doorway."""
    r = await db.execute(
        select(Doorway, Domain)
        .join(Domain, Doorway.domain_id == Domain.id)
        .where(Doorway.id == doorway_id)
    )
    row = r.first()
    if not row:
        return None
    dw, dom = row
    base = f"https://{dom.domain}".rstrip("/")
    path = dw.path or "/"
    return base if path == "/" else f"{base}{path}"
