"""Broken links: check and repair."""

import re
import asyncio
from typing import List
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doorway import Doorway
from app.models.domain import Domain
from app.models.campaign import Campaign


def extract_links(html: str) -> List[str]:
    """Extract href URLs from HTML."""
    return re.findall(r'href=["\'](https?://[^"\']+)["\']', html, re.I)


async def check_url(url: str, timeout: float = 5.0) -> tuple:
    """Check if URL returns 2xx. Returns (ok, status_code)."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.head(url, timeout=timeout)
            return 200 <= r.status_code < 400, r.status_code
    except Exception:
        return False, 0


async def find_broken_links(db: AsyncSession, doorway_id: int, content: str) -> List[dict]:
    """Check links in content. Returns list of {url, status, broken}."""
    links = extract_links(content)
    if not links:
        return []
    results = []
    for url in links[:20]:
        ok, status = await check_url(url)
        results.append({"url": url, "status": status, "broken": not ok})
        await asyncio.sleep(0.2)
    return results


def repair_broken_links_in_content(content: str, broken_urls: List[str], replacement: str = "#") -> str:
    """Replace broken URLs with replacement."""
    for url in broken_urls:
        content = re.sub(rf'href=["\']({re.escape(url)})["\']', f'href="{replacement}"', content, flags=re.I)
    return content
