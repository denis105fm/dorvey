# Мастер-план: Система умных дорвеев (полная версия)

> Объединённый план: базовая архитектура + расширенная максималка

---

## 1. Технологический стек

| Компонент | Технология |
|-----------|------------|
| Backend | Python 3.11+ / FastAPI |
| Frontend | React 18 + TypeScript + Vite |
| UI | shadcn/ui + Tailwind CSS |
| БД | PostgreSQL 15+ |
| Кэш/Очереди | Redis |
| Фоновые задачи | Celery |
| AI | OpenAI API (GPT-4o, GPT-4o-mini) |
| Собственный ML | scikit-learn, XGBoost (кластеризация, предсказания) |
| Хранилище | S3-совместимое (MinIO / Cloudflare R2) |
| Деплой дорвеев | SSH (paramiko), FTP |

---

## 2. Архитектура

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + Vite)                              │
│  Dashboard │ Campaigns │ Doorways │ Templates │ Analytics │ Settings     │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ REST API + WebSocket
┌───────────────────────────────────▼─────────────────────────────────────┐
│                        BACKEND (FastAPI)                                 │
│  Auth │ Campaigns │ Doorways │ Deploy │ Indexing │ Analytics │ AI        │
└───────┬───────────┬──────────┬────────┬──────────┬──────────┬────────────┘
        │           │          │        │          │          │
        ▼           ▼          ▼        ▼          ▼          ▼
┌─────────┐ ┌───────┐ ┌──────┐ ┌──────┐ ┌────────┐ ┌─────────────────────┐
│PostgreSQL│ │ Redis │ │Celery│ │OpenAI│ │ GSC    │ │ Voluum/Binom API    │
│         │ │       │ │      │ │ API  │ │ Bing   │ │ Postback            │
└─────────┘ └───────┘ └──────┘ └──────┘ └────────┘ └─────────────────────┘
                                    │
                        ┌───────────▼────────────┐
                        │  Deploy → Servers      │
                        │  (SSH/FTP)             │
                        └───────────────────────┘
```

---

## 3. Языки и регионы

- **Мультиязычность:** ru, en, de, es, pl, uk и др.
- **Поля в БД:** language, locale, region, currency
- **AI:** промпты с учётом языка и региона
- **Семантика:** локаль в GSC, hreflang, geo-теги

---

## 4. Модули системы

### 4.1 Базовые модули

| # | Модуль | Описание |
|---|--------|----------|
| 1 | Auth | Регистрация, логин, JWT, 2FA, роли |
| 2 | Campaigns | Партнёрки, домены, серверы, правила, язык/регион |
| 3 | Templates | Шаблоны страниц, блоков, стилей |
| 4 | Semantic | Ключевые слова, кластеры, импорт |
| 5 | Generator | AI-генерация контента (OpenAI) |
| 6 | Cloaking | Бот vs человек, версии контента |
| 7 | Deploy | SSH/FTP, SSL, привязка доменов |
| 8 | Indexing | GSC, Bing, sitemap, URL submission |
| 9 | Analytics | Позиции, трафик, CR, postback |
| 10 | AI Optimizer | Рекомендации, авто-правки, A/B |
| 11 | Admin Panel | Дашборд, CRUD, настройки |
| 12 | Notifications | Telegram, email, Slack |
| 13 | Billing | Лимиты, тарифы (опционально) |

### 4.2 Расширенные модули (Максималка)

| Модуль | Функции |
|--------|---------|
| **Управление офферами** | Автосмена при падении CR, geo/device-роутинг, API партнёрок, приоритет по ROI |
| **SEO-максимум** | Featured Snippets, PAA, Core Web Vitals, перелинковка, каннибализация, подбор доменов |
| **Конверсия-максимум** | Heatmaps, exit-intent, A/B layout'ов, trust-элементы, сравнительные таблицы |
| **Масштабирование** | Копирование победителей, авто-пауза убыточных, трафик-микс |
| **Самовосстановление** | Автооткат при падении CR, ремонт битых ссылок, SSL, пауза при проблемах партнёрки |
| **Автоматизация** | Конструктор правил, Webhooks, API, трекеры (Voluum), server-side трекинг |
| **Платформа** | White-label, мобильное приложение, расширение для браузера |
| **Anti-detection** | Structural randomization, deploy staggering, content quality, PAA/FAQ |

---

## 5. Структура БД

```sql
-- Users
users (id, email, password_hash, role, created_at, two_fa_secret)

-- Campaigns
campaigns (id, name, user_id, affiliate_url, affiliate_rules JSONB, 
  language, locale, region, currency, created_at, updated_at)

-- Servers
servers (id, name, host, port, user, auth_type, path, ssl_auto)

-- Domains
domains (id, domain, server_id, campaign_id, status, ssl_expires_at)

-- Doorways
doorways (id, campaign_id, domain_id, path, title, content, meta_description,
  cloaking_rules JSONB, status, created_at, deployed_at, indexed_at)

-- Versions (откат)
doorway_versions (id, doorway_id, content_snapshot JSONB, created_at)

-- Метрики
doorway_metrics (id, doorway_id, date, impressions, clicks, ctr, avg_position,
  conversions, revenue)

-- Keywords
keywords (id, campaign_id, keyword, cluster_id, volume)

-- Templates
templates (id, name, type, content, variables JSONB)

-- Offers (расширенное)
offers (id, campaign_id, url, geo, device, priority, is_active)
```

---

## 6. OpenAI vs Собственный AI

| Задача | OpenAI | Собственный ML |
|--------|--------|----------------|
| Генерация текста | ✓ | — |
| Заголовки, мета | ✓ | — |
| Анализ тона, правила | ✓ | — |
| Кластеризация ключей | — | ✓ |
| Предсказание CR/позиций | — | ✓ |
| Рекомендации | ✓ | ✓ |
| A/B выбор победителя | — | ✓ |
| Детекция аномалий | — | ✓ |

---

## 7. Roadmap разработки

### Фаза 0: Инфраструктура (1–2 нед) ✅
- Репозиторий, Docker, CI/CD
- Окружения dev/staging/prod

### Фаза 1: Ядро (3–4 нед) ✅
- Auth, Campaigns, Doorways, Servers, Domains
- CRUD API, базовый frontend
- Язык/регион в конфиге

### Фаза 2: Генерация (3–4 нед) ✅
- OpenAI интеграция ✅
- Шаблоны, Cloaking ✅
- Семантика, кластеризация ✅

### Фаза 3: Деплой (2–3 нед) ✅
- SSH/FTP deploy
- SSL, привязка доменов
- Health-check

### Фаза 4: Индексация (2 нед) ✅
- GSC API, Bing API
- Sitemap, URL submission

### Фаза 5: Аналитика (3–4 нед) ✅
- GSC метрики, Postback
- Дашборд, отчёты

### Фаза 6: AI-оптимизация (3–4 нед) ✅
- Рекомендации (`GET /optimizer/doorway/{id}/recommendations`), авто-правки (`POST /optimizer/doorway/{id}/apply-recommendation`)
- A/B winner, откат при падении CR, auto-rollback с учётом правил кампании

### Фаза 7: Пакетный режим (2–3 нед) ✅
- CSV импорт, авто-маппинг
- Массовая генерация

### Фаза 8: Расширенная максималка (4–6 нед) ✅
- Управление офферами, geo/device
- Featured Snippets, Core Web Vitals
- Heatmaps, exit-intent
- Самовосстановление, Webhooks
- Трекеры, white-label

### Фаза 9: Anti-detection (снижение риска блокировки) ✅
- **Стратегия:** `docs/ANTI_DETECTION_STRATEGY.md`
- Structural randomization: порядок блоков, layout-варианты, schema (Article/WebPage)
- Deploy staggering: batch deploy с паузами (`POST /api/deploy/batch`)
- Content quality: pre-deploy проверки (`GET /api/doorways/{id}/quality-check`)
- Trust badges: несколько вариантов (seed-based)
- PAA schema: `cloaking_rules.faq_qa` → JSON-LD FAQPage

### Фаза 10: Остаточная максималка ✅
- **2FA** — TOTP (setup, verify, disable)
- **S3/MinIO/R2** — хранилище (`app/services/storage.py`, env S3_*)
- **SEO:** перелинковка (`GET /api/seo/internal-links/{id}`), каннибализация (`GET /api/seo/cannibalization/{campaign_id}`), подбор доменов (`GET /api/seo/domains/suggest`)
- **Ремонт битых ссылок:** `GET /api/broken-links/doorway/{id}`, `POST .../repair`
- **Конструктор правил:** `GET/PUT /api/rules/campaign/{id}` (forbidden_words, allowed_geo, auto_switch_on_cr_drop и т.д.)
- **Пауза при проблемах партнёрки:** `POST /api/cron/pause-on-affiliate-issues`
- **ML:** предсказание CR (`GET /api/optimizer/doorway/{id}/predict-cr`), детекция аномалий (`GET /api/optimizer/anomalies`)
- **Billing:** лимиты, тарифы (`GET /api/billing/usage`, `GET /api/billing/plans`), план в Settings
- **shadcn/ui** — Button, Card в `frontend/src/components/ui/`
- **XGBoost** — в predict_cr при 10+ точках
- **Расширение браузера** — `extension/` (Chrome MV3, popup для токена)
- **Трафик-микс** — `GET /api/optimizer/campaign/{id}/traffic-mix`
- **Email** — SMTP, `email_notifications_enabled` в Settings
- **Users admin** — `GET /api/users/` (admin), страница Пользователи
- **Лимиты GSC** — 200 URL/час на пользователя (`gsc_ratelimit.py`)

### Backlog / К обсуждению: Внешняя аналитика для старта и выбора ниши

Цель: система сильнее опирается на **внешнюю** аналитику уже на этапе старта — подбор ниш и офферов до того, как накоплены свои клики/конверсии.

**Провайдеры подсказки ключей (выбор в Настройках):** в интерфейсе — выбор из списка с описанием и нужными полями. Можно начать с лимитированных/бесплатных, при прибыли перейти на платные.

| Провайдер | Регистрация | Что нужно в настройках | Описание |
|------------|-------------|------------------------|----------|
| **DataForSeo** | Платный, для компаний | Логин + пароль API (app.dataforseo.com) | Большая база ключей, объём по гео. Платный, часто только юрлица. |
| **FetchSERP** | Физлицо, 250 бесплатных кредитов | API ключ (fetchserp.com/app) | Подсказки ключей и объём по странам. Бесплатный старт, потом кредиты. |
| **Serper** | Физлицо, 2500 запросов в триале | API ключ | В основном SERP; при необходимости — доп. источник. |
| *(при необходимости добавить Serpstat и др.)* | | | |

**Полная автоматизация подсказок:** система сама подтягивает ключи из выбранного провайдера, отбирает по объёму/гео и вставляет в кампанию (без ручного «Подтянуть» → «Импортировать»). Реализовать в рамках пунктов 1 и 3 ниже.

| # | Идея | Описание |
|---|------|----------|
| 1 | **Стартовый набор ниш/ключей** | Запрос к выбранному провайдеру (DataForSeo/FetchSERP) по списку ниш/микрониш (из справочника или из офферов) → топ ключей по объёму/конкуренции. Опционально: авто-импорт в кампанию. |
| 2 | **Приоритет офферов при нулевых данных** | Сейчас «лучший оффер» только по нашему ROI. Добавить внешний сигнал для холодного старта: данные из API партнёрки (если есть) или эвристики по описанию оффера, гео, типу креатива. |
| 3 | **Авто-создание первой кампании из офферов** | Сценарий: офферы из партнёрки → по `offer-country-recommendations` выбрать гео → по выбранному провайдеру ключей сгенерировать ключи для этих гео/ниш → создать одну кампанию + N дорвеев. |
| 4 | **Сезонность из внешнего источника** | Сейчас сезонность только из опционального URL (свой JSON). Добавить автоматический источник: API или эвристика по странам/месяцам, учитывать в offer-country-recommendations. |

Связь с текущим функционалом:
- Внутренняя аналитика уже выбирает: лучший оффер по ROI, ранний стоп, traffic mix, прогноз CR, офферы из других кампаний.
- Внешняя уже используется: DataForSeo для подсказки ключей по семени (`suggest-from-external`), offer-country-recommendations (новости/сезонность). Нишу/ключи система пока не выбирает сама — только подсказывает ключи по заданной нише.

---

## 8. Конфиг кампании (полный)

```yaml
campaign:
  name: "Финансы RU"
  affiliate:
    url: "https://partner.com/offer?id=123"
    network: "partner_network"
    rules:
      forbidden_words: ["казино", "ставки"]
      allowed_geo: ["RU", "KZ", "BY"]
      require_disclaimer: true
  content:
    language: ru
    locale: ru-RU
    region: RU
    currency: RUB
  server_id: 1
  domains: ["domain1.ru", "domain2.ru"]
  cloaking:
    enabled: true
    bot_patterns: ["Googlebot", "Yandexbot", "Bingbot"]
  indexing:
    gsc_property: "https://domain1.ru/"
    auto_submit: true
  ai:
    optimization_enabled: true
    ab_tests: true
    min_days_before_optimize: 7
    auto_rollback_on_cr_drop: true
    rollback_threshold_percent: 15
  offers:
    geo_routing: true
    device_optimization: true
    auto_switch_on_cr_drop: true
```

---

## 9. Админ-панель: страницы

- Dashboard (сводка, топ, алерты)
- Campaigns (CRUD, шаблоны)
- Doorways (список, фильтры, действия)
- Servers (CRUD)
- Domains (список, SSL)
- Templates (библиотека)
- Semantic (ключи, кластеры)
- Analytics (графики, таблицы)
- Offers (офферы, geo, device)
- Settings (GSC, уведомления, API)
- Users (если multi-user)
