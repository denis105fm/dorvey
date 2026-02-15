"""OpenAI service for content generation."""

import json
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings


class OpenAIService:
    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY or "sk-dummy")
        return self._client

    def get_client_for_key(self, api_key: Optional[str] = None) -> AsyncOpenAI:
        """Use user's API key from Settings, or fallback to env."""
        key = (api_key or "").strip()
        if key:
            return AsyncOpenAI(api_key=key)
        return self.client

    def is_available(self, api_key_override: Optional[str] = None) -> bool:
        key = (api_key_override or "").strip()
        if key:
            return True
        return bool(settings.OPENAI_API_KEY)

    async def generate_doorway_content(
        self,
        *,
        keyword: str,
        language: str = "ru",
        region: str = "RU",
        affiliate_url: Optional[str] = None,
        forbidden_words: Optional[list[str]] = None,
        tone: str = "informative",
        api_key_override: Optional[str] = None,
    ) -> dict[str, str]:
        """Generate title, meta_description, and content for doorway."""
        client = self.get_client_for_key(api_key_override)
        forbidden_str = ""
        if forbidden_words:
            forbidden_str = f"\n\nЗАПРЕЩЕНО использовать: {', '.join(forbidden_words)}"

        system_prompt = f"""Ты — профессиональный SEO-копирайтер. Создаёшь ценный контент для лендинга.
Язык: {language}. Регион: {region}. Стиль: {tone}.

Правила: закрывай поисковый интент полностью. Минимум 400 слов в content (2-4 абзаца + H1). Естественный язык, без шаблонных фраз ("в данной статье", "мы расскажем", "подводя итоги").
- title: 50-60 символов, цепляющий, с ключевым словом
- meta_description: 140-160 символов, призыв к действию
- content: валидный HTML. <p>, <h1>. Без лишних div
{forbidden_str}

Ответ — только валидный JSON: {{"title": "...", "meta_description": "...", "content": "..."}}"""

        user_prompt = f'Ключевой запрос: "{keyword}"'
        if affiliate_url:
            user_prompt += f"\nСсылка оффера: {affiliate_url}"

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,
        )
        text = (response.choices[0].message.content or "{}").strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1][4:] if parts[1].startswith("json") else parts[1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "title": f"{keyword} | Лучшие предложения",
                "meta_description": f"Узнайте о {keyword}. Выгодные условия.",
                "content": f"<h1>{keyword}</h1><p>Информация по запросу {keyword}.</p>",
            }


openai_service = OpenAIService()
