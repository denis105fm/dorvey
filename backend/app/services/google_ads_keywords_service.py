"""Google Ads API (Keyword Plan Idea Service) for keyword suggestions and search volume.

Подсказки ключей и объём поиска через Google Ads API.
Требуется: Developer Token, OAuth (client_id, client_secret, refresh_token).
Документация: https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


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
