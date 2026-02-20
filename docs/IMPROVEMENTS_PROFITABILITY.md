# Улучшения рентабельности дорвеев

Документ описывает добавленные функции для повышения прибыли от дорвеев.

---

## 1. Копирование победителей

**Что:** Копирование контента (title, content, meta_description) с лучшего по CR дорвея на целевой.

**Где:** Кампании → кнопка «Copy winner» → выбрать кампанию → указать источник (0 = авто-выбор по CR) и целевой дорвей → «Скопировать».

**API:** `POST /api/optimizer/campaign/{id}/copy-winner` с `{ source_doorway_id, target_doorway_id }`.  
При `source_doorway_id=0` — автоматический выбор лучшего по CR (min 20 кликов).

**Эффект:** Быстрое применение выигрышного контента на новые дорвеи без ручной копипасты.

---

## 2. GSC Fetch — импорт показов и кликов

**Что:** Загрузка impressions/clicks из Google Search Console Search Analytics API в DoorwayMetrics.

**Где:** SEO → блок «GSC Fetch» → выбрать домен, указать GSC property (sc-domain:example.com), дни → «Импорт из GSC».

**Требования:** GSC credentials в Настройках (Client ID, Secret, Refresh Token). OAuth scope: webmasters.readonly.

**API:** `POST /api/indexing/gsc-fetch` с `{ domain_id, site_url, days }`.

**Эффект:** Метрики из GSC попадают в DoorwayMetrics — аналитика, Predict CR, A/B winner и рекомендации работают точнее.

---

## 3. Алерты при аномалиях (падение CR)

**Что:** При обнаружении аномалий (падение CR, нулевые конверсии) отправляются уведомления в Telegram, Slack, Email и webhooks.

**Событие:** `doorway.anomaly` — payload: `{ doorway_id, type, severity, message }`.

**Как:** Cron `run-all` включает `run_anomaly_alerts` — ежедневно для каждого пользователя вызывается `detect_anomalies` и при наличии аномалий — `notify_webhooks` с событием `doorway.anomaly`.

**Эффект:** Быстрая реакция на падение CR без ручной проверки.

---

## 4. Сводка воронки в аналитике

**Что:** В ответ `/api/analytics/summary` добавлены `ctr_percent` и `cr_percent`.

**Где:** Дашборд — метрики «CTR %» и «CR %».

**Эффект:** Воронка показы → клики → конверсии видна сразу.

---

## 5. Фильтр ботов (postback)

**Что:** Ограничение на количество postback'ов в минуту с одного дорвея — защита от накрутки.

**Параметры:** Макс. 20 postback'ов в минуту на один doorway_id. При превышении возвращается `{"status":"ignored","reason":"rate_limit_suspected_bot"}`.

**Эффект:** Снижение влияния фейковых конверсий.

---

## События webhook

| Событие | Когда |
|---------|-------|
| doorway.deployed | Дорвей задеплоен |
| doorway.conversion | Конверсия (postback) |
| doorway.rollback | Откат контента |
| doorway.anomaly | Аномалия (падение CR, нулевые конверсии) |
| doorway.copy_winner | Контент скопирован с победителя |
| doorway.auto_paused | Дорвей автоматически поставлен на паузу |
