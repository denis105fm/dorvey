# Интеграция FetchSERP API (Keywords Suggestions)

Документ для передачи в support@fetchserp.com при отладке HTTP 500.

---

## 1. Файлы, где используется FetchSERP

| Файл | Назначение |
|------|------------|
| `backend/app/services/fetchserp_service.py` | HTTP-запросы к FetchSERP, разбор ответа |
| `backend/app/api/keywords.py` | Вызов сервиса при «Подтянуть ключи» / «Авто-подтянуть» |
| `backend/app/api/campaigns.py` | Вызов при создании кампании с seed-ключами |
| `backend/app/api/settings.py` | Проверка ключа (GET /api/v1/user) |
| `backend/app/services/settings_helpers.py` | Чтение `fetchserp_api_key` из настроек |
| `frontend/src/pages/Settings.tsx` | UI: выбор провайдера FetchSERP, поле API Key, кнопка «Проверить» |
| `frontend/src/pages/Keywords.tsx` | UI: блок «Авто-подтянуть ключи», вывод debug в консоль |

---

## 2. Функция, которая делает HTTP-запрос

**Файл:** `backend/app/services/fetchserp_service.py`  
**Функция:** `fetch_keywords_for_keywords(api_key, *, seed, country="US", limit=100)`

Используется библиотека **httpx** (async). Запрос — **GET**, без тела (body). Параметры передаются в **query string**.

---

## 3. Полный HTTP-запрос к FetchSERP

### Метод
**GET**

### URL (endpoint)
Базовый URL задаётся переменной окружения **`FETCHSERP_API_BASE`** (по умолчанию `https://api.fetchserp.com`).  
Раньше использовался `https://www.fetchserp.com` — на нём keywords_suggestions отдавал 500; api-поддомен часто используется для реального API.

Полный URL запроса: `{FETCHSERP_API_BASE}/api/v1/keywords_suggestions`

### Query-параметры (формат: query params, не JSON body)
- `country` — **всегда в нижнем регистре** (us, ru). В коде UI может быть "US", сервис приводит через `_country_code()` к `us`.
- `keywords` — повторяемый параметр: одна или несколько seed-фраз.  
  Пример для одной фразы: `keywords=casual%20clicker%20game`.  
  Для нескольких: `keywords=phrase1&keywords=phrase2`.  
  Пустые/короткие части не отправляются (чтобы не провоцировать 500 на пустом вводе).

**Пример полного URL запроса (без ключа):**
```
https://api.fetchserp.com/api/v1/keywords_suggestions?country=us&keywords=casual+clicker+game
```
(При `FETCHSERP_API_BASE=https://www.fetchserp.com` будет www.)

### Headers
```
Authorization: Bearer <API_KEY>
Accept: application/json
User-Agent: Dorvey/1.0 (+https://github.com/denis105fm/dorvey)
```

### Body
**Нет.** Метод GET, тело запроса не передаётся.

### Как передаётся API key
В **заголовке** `Authorization: Bearer <API_KEY>` (не в query, не в body).

---

## 4. Код запроса (фрагмент)

```python
url = "https://www.fetchserp.com/api/v1/keywords_suggestions"
params = [("country", cc)]   # cc = "us" для US
for kw in seed_parts[:10]:
    params.append(("keywords", kw))

async with httpx.AsyncClient(timeout=30.0) as client:
    r = await client.get(
        url,
        params=params,
        headers={
            "Authorization": f"Bearer {key_clean}",
            "Accept": "application/json",
            "User-Agent": "Dorvey/1.0 (+https://github.com/denis105fm/dorvey)",
        },
    )
```

---

## 5. Ожидаемый ответ (по документации FetchSERP)

**Успех (200):** Поддерживаются два формата ответа (из-за рассинхрона версий/доки):
- С вложением: `data.keywords_suggestions` (официальная схема),
- Топ-уровень: `keywords_suggestions` (как в публичных примерах).

В коде парсятся оба варианта.

```json
{
  "data": {
    "keywords_suggestions_count": 42,
    "keywords_suggestions": [
      {
        "keyword": "casual clicker games",
        "avg_monthly_searches": 1000,
        "competition": "LOW",
        "competition_index": 12,
        "low_top_of_page_bid_micros": 500000,
        "high_top_of_page_bid_micros": 800000
      }
    ]
  }
}
```

**Фактически получаем:** HTTP **500 Internal Server Error** (тело обычно `Internal Server Error` или пустое).  
При 500 в нашем коде в лог пишется: `request_url`, `response_preview` (первые 500 символов ответа).

---

## 6. Дополнительно: проверка ключа (не keywords_suggestions)

**Endpoint:** `GET https://www.fetchserp.com/api/v1/user`  
**Headers:** те же (`Authorization: Bearer <KEY>`, `Accept: application/json`, `User-Agent`).  
**Body:** нет.  
Этот запрос выполняется при нажатии «Проверить» в Настройках и возвращает **200** с информацией о кредитах — то есть ключ принимается.

---

## 7. Кратко для support@fetchserp.com

- **Endpoint:** `GET /api/v1/keywords_suggestions`
- **Параметры:** `country=us`, `keywords=casual clicker game` (в query string).
- **Авторизация:** заголовок `Authorization: Bearer <API_KEY>`.
- **Результат:** HTTP 500 Internal Server Error, ключ валидный (GET /api/v1/user возвращает 200).
- Нужно: понять причину 500 для этого запроса (формат параметров, лимиты, ошибка на стороне сервера).
