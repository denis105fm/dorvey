"""FetchSERP API service for keyword suggestions and volume."""

import httpx

# ISO country code (uppercase) -> FetchSERP country (lowercase, as in their API)
COUNTRY_TO_FETCHSERP: dict[str, str] = {
    "RU": "ru", "US": "us", "KZ": "kz", "BY": "by", "UA": "ua",
    "DE": "de", "FR": "fr", "GB": "gb", "PL": "pl", "IT": "it",
    "ES": "es", "TR": "tr", "IN": "in", "BR": "br", "MX": "mx",
    "AR": "ar", "CO": "co", "ID": "id", "VN": "vn", "TH": "th",
    "PH": "ph", "EG": "eg", "ZA": "za", "NG": "ng", "KE": "ke",
    "CA": "ca", "AU": "au", "NL": "nl", "CH": "ch",
}


def _country_code(country: str) -> str:
    c = (country or "us").strip().upper()[:2]
    return COUNTRY_TO_FETCHSERP.get(c, "us")


async def fetch_keywords_for_keywords(
    api_key: str,
    *,
    seed: str,
    country: str = "US",
    limit: int = 100,
) -> list[dict]:
    """
    Fetch keyword suggestions from FetchSERP keywords_suggestions API.
    Returns list of dicts: {keyword, volume, cpc}.
    """
    if not (api_key or "").strip():
        return []
    seed_clean = (seed or "").strip()[:200]
    if not seed_clean:
        return []
    cc = _country_code(country)
    url = "https://www.fetchserp.com/api/v1/keywords_suggestions"
    params = {"keywords": seed_clean, "country": cc}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {api_key.strip()}"},
        )
    if r.status_code != 200:
        return []
    data = r.json()
    # Response may be { "keyword_suggestions": [ { "keyword", "search_volume", "cpc" } ] } or similar
    raw_list = (
        data.get("keyword_suggestions")
        or data.get("keywords")
        or data.get("data")
        or (data if isinstance(data, list) else [])
    )
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw_list[:limit]:
        if isinstance(item, str):
            kw = item.strip()
            vol, cpc = 0, 0.0
        else:
            kw = (item.get("keyword") or item.get("key") or item.get("query") or "").strip()
            vol = item.get("search_volume") or item.get("volume") or item.get("search_volume_avg") or 0
            cpc = item.get("cpc") or item.get("avg_cpc") or 0.0
        if not kw or kw.lower() in seen:
            continue
        seen.add(kw.lower())
        try:
            vol = int(vol)
        except (TypeError, ValueError):
            vol = 0
        try:
            cpc = float(cpc)
        except (TypeError, ValueError):
            cpc = 0.0
        out.append({"keyword": kw, "volume": vol, "cpc": cpc})
    return out
