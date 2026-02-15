# План улучшений: максимальная автоматизация

## Приоритет 1 — Сделано

- [x] Доп. шаблоны (миграция 005): Минималистичный, Финансовый
- [x] Endpoint `POST /api/cron/run-all` — запуск всех daily-задач одним вызовом
- [x] Celery Beat — периодические задачи (auto-generate, run-cron)
- [x] Auto-generate: генерация дорвеев из ключевых слов кампании

## Приоритет 2 — Рекомендуется

- [ ] **GSC Fetch** — импорт impressions/clicks из GSC API в DoorwayMetrics (сейчас только postback)
- [ ] **Auto-apply recommendations** — при падении CTR/CR ниже порога вызывать apply_recommendation
- [ ] **Template editor в UI** — создание/редактирование шаблонов (сейчас только API)
- [x] **Правила по умолчанию** — seed affiliate_rules для новых кампаний (auto_rollback_on, min_days) — сделано
- [ ] **Wizard первого запуска** — создание кампании + домен + ключи за 3 шага

## Приоритет 3 — Улучшения

- [x] **Trust badge variants** — 8 RU, 7 EN, DE/ES/PL в schema_helper, seed-based выбор — сделано
- [ ] **PAA/FAQ в генераторе** — AI генерирует FAQ, кладёт в cloaking_rules.faq_qa
- [ ] **Копирование победителей** — копировать layout/content победителя A/B на новые дорвеи
- [ ] **Лимиты и алерты** — уведомление при достижении лимита дорвеев, падении видимости

## Включение auto-generate

В настройках кампании (Rules / affiliate_rules) установи:

```json
{"auto_generate_enabled": true}
```

Или через API: `PUT /api/rules/campaign/{id}` с `{"auto_generate_enabled": true}`.

Тогда Celery Beat будет ежедневно генерировать дорвеи из ключевых слов (до 5 на кампанию, 20 всего за запуск).

## Cron (внешний)

Вариант 1 — один endpoint:

```bash
# Ежедневно в 3:00 — все оптимизации
0 3 * * * curl -X POST "https://your-app/api/cron/run-all"
```

Вариант 2 — Celery Beat (рекомендуется): запусти `celery-beat` в docker-compose. Он сам вызовет:
- `cron_run_all` — ежедневно в 3:00
- `auto_generate_from_keywords` — ежедневно в 4:30
