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
        external_context: Optional[str] = None,
        tone: str = "informative",
        is_black: bool = False,
        api_key_override: Optional[str] = None,
    ) -> dict[str, str]:
        """Generate title, meta_description, and content for doorway."""
        client = self.get_client_for_key(api_key_override)
        forbidden_str = ""
        if forbidden_words:
            forbidden_str = f"\n\nЗАПРЕЩЕНО использовать: {', '.join(forbidden_words)}"

        black_hint = ""
        if is_black:
            black_hint = """

Режим чёрных дорвеев (максимальный охват поиска, но чтобы жили дольше — не палиться ботам):
- Контент для поисковика остаётся информативным и естественным. Избегай шаблонов: разная длина предложений и абзацев, вариативность формулировок, мягкое использование LSI-слов и синонимов в тексте — так сложнее детектить.
- Допустимы более жёсткие призывы к действию и акцент на выгоду для пользователя. Для поиска — полезный текст; для конверсии — чёткий CTA.
- ОБЯЗАТЕЛЬНО добавь поле "seo_tail" в JSON: одна строка (до 400 символов) с 15–25 семантическими вариациями и длиннохвостыми запросами по теме. Формат: естественная фраза или перечисление через запятую/точку с запятой, как блок «похожие темы» или «ещё по теме». Не дублируй основной ключ дословно — только синонимы, смежные запросы, длинный хвост. Цель — усилить охват в поиске без явного переспама. Пример тона: «Также в разделе: запрос 1, запрос 2, запрос 3»."""

        json_fields = '{"title": "...", "meta_description": "...", "content": "..."}'
        if is_black:
            json_fields = '{"title": "...", "meta_description": "...", "content": "...", "seo_tail": "похожие темы: вариация1, вариация2, ..."}'

        system_prompt = f"""Ты — профессиональный SEO-копирайтер. Создаёшь ценный контент для лендинга.
Язык: {language}. Регион: {region}. Стиль: {tone}.

Правила: закрывай поисковый интент полностью. Минимум 400 слов в content (2-4 абзаца + H1). Естественный язык, без шаблонных фраз ("в данной статье", "мы расскажем", "подводя итоги").
- title: 50-60 символов, цепляющий, с ключевым словом
- meta_description: 140-160 символов, призыв к действию
- content: валидный HTML. <p>, <h1>. Без лишних div
{forbidden_str}
Если в запросе пользователя дан контекст по региону (сезонность, актуальные темы) — можешь мягко учесть в заголовке или в одном предложении в тексте. Не перегружай: одно упоминание или тон достаточно. Контент должен оставаться про ключевой запрос.
{black_hint}

Ответ — только валидный JSON: {json_fields}"""

        user_prompt = f'Ключевой запрос: "{keyword}"'
        if affiliate_url:
            user_prompt += f"\nСсылка оффера: {affiliate_url}"
        if external_context and external_context.strip():
            user_prompt += f"\n\nКонтекст по региону (использовать по желанию, не перегружать):\n{external_context.strip()}"

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.75 if is_black else 0.6,
        )
        text = (response.choices[0].message.content or "{}").strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1][4:] if parts[1].startswith("json") else parts[1]
        try:
            out = json.loads(text)
            if is_black and isinstance(out, dict) and out.get("seo_tail"):
                out["seo_tail"] = str(out["seo_tail"]).strip()[:500]
            return out
        except json.JSONDecodeError:
            result = {
                "title": f"{keyword} | Лучшие предложения",
                "meta_description": f"Узнайте о {keyword}. Выгодные условия.",
                "content": f"<h1>{keyword}</h1><p>Информация по запросу {keyword}.</p>",
            }
            if is_black:
                result["seo_tail"] = ""
            return result

    async def generate_faq(
        self,
        *,
        keyword: str,
        language: str = "ru",
        max_items: int = 8,
        api_key_override: Optional[str] = None,
    ) -> list[dict[str, str]]:
        """Generate 5-8 Q&A pairs for PAA/FAQ schema (People Also Ask). Returns list of {question, answer}."""
        client = self.get_client_for_key(api_key_override)
        system_prompt = f"""Ты — SEO-копирайтер. Создаёшь короткие вопросы и ответы для блока "Часто спрашивают" (FAQ) на странице.
Язык: {language}. Тема: запрос пользователя.

Правила: вопросы — как в поиске (People Also Ask). Ответы — 1-3 предложения, по делу. Без рекламы.
Ответ — только валидный JSON массив: [{{"question": "...", "answer": "..."}}, ...]
Минимум 5, максимум {max_items} пар."""

        user_prompt = f'Тема/ключевой запрос: "{keyword}"'

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
        )
        text = (response.choices[0].message.content or "[]").strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1][4:] if len(parts) > 1 and parts[1].startswith("json") else parts[1]
        try:
            arr = json.loads(text)
            if not isinstance(arr, list):
                return []
            out = []
            for item in arr[:max_items]:
                if isinstance(item, dict) and item.get("question") and item.get("answer"):
                    out.append({"question": str(item["question"])[:200], "answer": str(item["answer"])[:500]})
            return out
        except json.JSONDecodeError:
            return []

    async def generate_quiz(
        self,
        *,
        keyword: str,
        language: str = "ru",
        offer_theme: Optional[str] = None,
        max_questions: int = 5,
        api_key_override: Optional[str] = None,
    ) -> list[dict]:
        """Generate 3–5 quiz questions (question + options) for doorway. Topic from keyword + offer_theme.
        Returns list of {question: str, options: [str]} (2–4 options per question). No 'correct' — flow leads to CTA."""
        client = self.get_client_for_key(api_key_override)
        theme = keyword
        if offer_theme and str(offer_theme).strip():
            theme = f"{keyword}. Тема оффера: {offer_theme.strip()}"
        system_prompt = f"""Ты — копирайтер. Создаёшь короткий квиз для лендинга: несколько вопросов с вариантами ответа.
Язык: {language}.

Правила:
- Вопросы по теме запроса, логично подводят к действию (оформить заявку / получить предложение).
- 3–5 вопросов. У каждого вопроса 2–4 варианта ответа (короткие фразы).
- Без правильных/неправильных ответов — любой выбор ведёт дальше.
- Ответ — только валидный JSON массив: [{{"question": "...", "options": ["...", "..."]}}, ...]
- question до 120 символов, каждый option до 60 символов."""

        user_prompt = f'Тема квиза: "{theme}"'

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
        )
        text = (response.choices[0].message.content or "[]").strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1][4:] if len(parts) > 1 and parts[1].strip().lower().startswith("json") else parts[1]
        try:
            arr = json.loads(text)
            if not isinstance(arr, list):
                return []
            out = []
            for item in arr[:max_questions]:
                if isinstance(item, dict) and item.get("question") and isinstance(item.get("options"), list):
                    opts = [str(o)[:60] for o in item["options"][:4] if o]
                    if len(opts) >= 2:
                        out.append({"question": str(item["question"])[:120], "options": opts})
            return out
        except json.JSONDecodeError:
            return []

    async def generate_affiliate_recommendations(
        self,
        *,
        keyword: str,
        language: str = "ru",
        region: str = "RU",
        max_items: int = 5,
        api_key_override: Optional[str] = None,
    ) -> list[dict]:
        """Recommend 3-5 affiliate networks for the niche. Returns list of {name, network, why, priority}."""
        client = self.get_client_for_key(api_key_override)
        system_prompt = f"""Ты — эксперт по партнёрскому маркетингу в РФ/СНГ. Рекомендуешь партнёрские сети (CPA-сети, офферы) для ниши.
Язык: {language}. Регион: {region}.

Правила: называй реальные сети (LeadGid, Admitad, M1-shop, ePN, Actionpay, Advertur, RichLeads, CPA.RBC и др.). Кратко — почему подходят для ниши.
Ответ — только валидный JSON массив: [{{"name": "название оффера/программы", "network": "название партнёрской сети", "why": "почему подходит", "priority": 1-5}}]
Минимум 3, максимум {max_items} элементов. priority=1 — лучший вариант."""

        user_prompt = f'Ниша/ключевое слово: "{keyword}"'

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
        )
        text = (response.choices[0].message.content or "[]").strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1][4:] if len(parts) > 1 and parts[1].startswith("json") else parts[1]
        try:
            arr = json.loads(text)
            if not isinstance(arr, list):
                return []
            out = []
            for item in arr[:max_items]:
                if isinstance(item, dict) and item.get("network"):
                    out.append({
                        "name": str(item.get("name", item.get("network", "")))[:100],
                        "network": str(item.get("network", ""))[:80],
                        "why": str(item.get("why", ""))[:300],
                        "priority": int(item.get("priority", 3)) if isinstance(item.get("priority"), (int, float)) else 3,
                    })
            return sorted(out, key=lambda x: x.get("priority", 5))
        except json.JSONDecodeError:
            return []


openai_service = OpenAIService()
