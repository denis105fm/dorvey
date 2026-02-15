# Cron и автоматизация

## Endpoints

| Endpoint | Описание | Параметры |
|----------|----------|-----------|
| `POST /api/cron/run-all` | Запуск всех daily-задач одним вызовом | — |
| `POST /api/cron/auto-rollback` | Откат при падении CR | threshold_percent, min_days |
| `POST /api/cron/auto-pause-unprofitable` | Пауза убыточных дорвеев | — |
| `POST /api/cron/auto-switch-offers` | Смена офферов при падении CR | — |
| `POST /api/cron/pause-on-affiliate-issues` | Пауза при проблемах партнёрки | — |

## Что делает run-all

`POST /api/cron/run-all` последовательно вызывает:

1. **auto-rollback** — откат doorway на предыдущую версию, если CR упал на ≥ `rollback_threshold_percent` (из affiliate_rules) и прошло ≥ `min_days_before_optimize`.
2. **auto-pause-unprofitable** — ставит status = paused для убыточных по ROI.
3. **auto-switch-offers** — меняет оффер на альтернативный при падении CR (если настроено).
4. **pause-on-affiliate-issues** — пауза при детекте проблем партнёрки.

Правила берутся из `affiliate_rules` кампании: `auto_rollback_on_cr_drop`, `rollback_threshold_percent`, `min_days_before_optimize`.

## Внешний cron

```bash
# Ежедневно в 3:00 (пример)
0 3 * * * curl -X POST "https://your-app/api/cron/run-all" -H "Authorization: Bearer $TOKEN"
```

Без токена — если endpoint публичный или защищён cron-secret (зависит от конфигурации).

## Celery Beat (встроенный)

При запуске `celery-beat` задачи выполняются автоматически:

| Задача | Расписание | Описание |
|--------|------------|----------|
| `cron_run_all` | 3:00 (cron) | Вызывает POST /api/cron/run-all |
| `auto_generate_from_keywords` | 4:30 (cron) | Генерация дорвеев из ключей кампании |

### auto_generate_from_keywords

- Обрабатывает кампании с `affiliate_rules.auto_generate_enabled = true`.
- Берёт keywords без привязанного doorway.
- Генерирует до 20 дорвеев за запуск (лимит на всю систему).
- Рекомендуемый лимит: до 5 на кампанию.

### Включение auto-generate

В Rules кампании: `PUT /api/rules/campaign/{id}` с `{"auto_generate_enabled": true}`.

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `CELERY_BROKER_URL` | Redis URL для Celery |
| `REDIS_URL` | Redis для кэша/сессий |

## Логи и отладка

- Celery worker: `docker compose logs -f celery`
- Celery beat: `docker compose logs -f celery-beat`
- При ошибках проверьте подключение к Redis и доступность backend API.
