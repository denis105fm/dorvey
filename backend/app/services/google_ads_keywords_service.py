"""Google Ads API (Keyword Plan Idea Service) for keyword suggestions and search volume.

Подсказки ключей и объём поиска через Google Ads API.
Требуется: Developer Token, OAuth (client_id, client_secret, refresh_token).
Документация: https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def validate_google_ads_credentials(creds: dict) -> tuple[bool, str]:
    """
    Проверка учётки: обмен refresh_token на access_token.
    creds: dict с ключами developer_token, client_id, client_secret, refresh_token.
    """
    cid = (creds.get("client_id") or "").strip()
    secret = (creds.get("client_secret") or "").strip()
    refresh = (creds.get("refresh_token") or "").strip()
    if not cid or not secret or not refresh:
        return False, "Заполните Client ID, Client Secret и Refresh Token и сохраните настройки."
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": cid,
                    "client_secret": secret,
                    "refresh_token": refresh,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if r.status_code != 200:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            err = body.get("error_description") or body.get("error") or r.text[:200]
            return False, err or f"HTTP {r.status_code}"
        data = r.json()
        if not data.get("access_token"):
            return False, "Не получен access_token"
        return True, "Подключение успешно. Учётные данные действительны."
    except Exception as e:
        msg = str(e).lower()
        if "401" in msg or "invalid" in msg or "invalid_grant" in msg:
            return False, "Неверный или истёкший Refresh Token. Получите новый (кнопка «Получить refresh token»)."
        return False, str(e)[:150]


async def fetch_keywords_for_keywords(
    developer_token: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    seed: str,
    country: str = "US",
    limit: int = 100,
) -> tuple[list[dict], dict[str, Any] | None]:
    """
    Заглушка: запросы к Google Ads API будут реализованы после настройки учётных данных.
    Возвращает (пустой список, debug_info с сообщением).
    """
    # TODO: реализовать OAuth2 refresh, вызов KeywordPlanIdeaService.GenerateKeywordIdeas,
    # маппинг country -> geo_target_constants, парсинг объёма и CPC из ответа.
    _ = (developer_token, client_id, client_secret, refresh_token, seed, country, limit)
    logger.info(
        "Google Ads API: заглушка (реализация в разработке). seed=%s country=%s",
        seed[:50], country,
    )
    debug = {
        "message": "Google Ads API пока не реализован. Заполните Developer Token и OAuth в Настройках; после завершения регистрации в Google Ads реализация запросов будет добавлена.",
    }
    return [], debug
