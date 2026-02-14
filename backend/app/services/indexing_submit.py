"""Submit URLs to GSC and Bing for indexing."""

import asyncio
from typing import Optional

import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError


async def submit_to_gsc(
    url: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> tuple[bool, str]:
    """
    Submit URL to Google Search Console Indexing API.
    Uses OAuth2 refresh token flow.
    Returns (success, message).
    """
    if not all([client_id, client_secret, refresh_token]):
        return False, "GSC credentials missing"
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

        access_token = await asyncio.to_thread(_refresh)
    except RefreshError as e:
        return False, f"GSC token refresh failed: {e}"
    except Exception as e:
        return False, f"GSC auth error: {e}"

    api_url = "https://indexing.googleapis.com/v3/urlNotifications:publish"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"url": url, "type": "URL_UPDATED"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(api_url, json=payload, headers=headers, timeout=10.0)
            if 200 <= r.status_code < 300:
                return True, "Submitted to GSC"
            return False, f"GSC API error {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)


async def submit_to_bing(url: str, api_key: str, site_url: Optional[str] = None) -> tuple[bool, str]:
    """
    Submit URL to Bing Webmaster API.
    site_url: base site URL (e.g. https://example.com) — derived from url if not set.
    Returns (success, message).
    """
    if not api_key:
        return False, "Bing API key missing"
    if not site_url:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        site_url = f"{parsed.scheme}://{parsed.netloc}"
    api_url = f"https://ssl.bing.com/webmaster/api.svc/json/SubmitUrl?apikey={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {"siteUrl": site_url, "url": url}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(api_url, json=payload, headers=headers, timeout=10.0)
            if 200 <= r.status_code < 300:
                return True, "Submitted to Bing"
            return False, f"Bing API error {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)
