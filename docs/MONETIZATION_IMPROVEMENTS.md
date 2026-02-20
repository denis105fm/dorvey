# Улучшения заработка на дорвеях

Исследование области монетизации дорвеев и рекомендации по повышению вероятности заработать.

---

## Текущее состояние Dorvey

| Компонент | Статус |
|-----------|--------|
| Postback (sub_id = doorway_id) | ✅ Есть |
| Копирование победителей (Copy winner) | ✅ Есть |
| GSC Fetch, метрики CTR/CR | ✅ Есть |
| Алерты при аномалиях | ✅ Есть |
| Exit-intent, trust-элементы | ✅ Есть |
| A/B контент (варианты) | ✅ Есть |
| GEO/device скрипт, cta_by_device | ✅ Есть |
| Офферы geo/device (Offers) | ⚠️ Только priority, не по GEO/device при рендере |
| sub_id в affiliate URL | ❌ Нет — ссылка без doorway_id |
| Heatmaps (Hotjar/Clarity) | ✅ Настройки есть |

---

## 1. sub_id в affiliate URL ✅

**Реализовано.** При рендере в affiliate URL подставляется `sub_id=doorway_id`:
- Поддерживаются placeholders `{sub_id}` и `{doorway_id}` — заменяются на doorway_id
- Иначе добавляется query-параметр `sub_id=123`

**Эффект:** Конверсии корректно привязываются к дорвеям, работают аналитика, CR, Copy winner, алерты.

---

## 2. Urgency и scarcity (срочность, дефицит) ✅

**Реализовано.** Блок urgency в cloaking_rules или campaign.settings:
- `urgency_block`: `{ "text": "Одобрение за 5 минут" }` или строка
- Рендерится жёлтым блоком перед/после CTA (порядок — через block_order)

---

## 3. Social proof (социальное доказательство) ✅

**Реализовано.** Блок social_proof в cloaking_rules или campaign.settings:
- `social_proof`: `{ "stats": "12 450 одобрений", "reviews": ["Отличный сервис", "Быстрое одобрение"] }` или строка
- Рендерится блоком с цифрами и отзывами (до 3 отзывов)

---

## 4. GEO/device роутинг офферов на клиенте ✅

**Реализовано.** При 2+ офферах с geo/device:
- В data-атрибуты CTA передавать JSON с офферами: `data-offers='[{"url":"...","geo":"RU","device":"mobile"},...]'`
- Скрипт после добавления `device-mobile` / `geo-RU` выбирает подходящий оффер и обновляет `href` у ссылок
- Fallback: affiliate_url кампании, если нет совпадения

**Эффект:** Разные офферы для RU/KZ, mobile/desktop, что повышает конверсию по нишам.

---

## 5. Несколько CTA на странице ✅

**Реализовано.** Блок `cta_footer` — второй CTA в конце страницы, sticky на mobile (закреплён внизу экрана).

---

## 6. A/B тест CTA-текста

**Идея:** A/B по тексту кнопки («Оформить заявку» vs «Получить деньги») и измерение CR.

**Реализация:** `content_variants` уже есть. Добавить поле `cta_text` в вариант — при применении варианта менять не только title/content, но и CTA. Либо отдельный A/B по CTA с привязкой к sub_id (sub_id = doorway_id + cta_variant).

---

## 7. Клик-трекинг (клики по CTA) ✅

**Реализовано.** Опционально через настройки:
- **Клик-трекинг включён** + **API Base URL** — CTA ведёт на `/api/analytics/click?dw=123`
- Endpoint: GET `/api/analytics/click?dw=123` — увеличивает clicks в DoorwayMetrics, редирект 302 на affiliate_url с sub_id
- Без настроек — CTA ведёт напрямую на affiliate_url с sub_id

---

## 8. Текст exit-intent ✅

**Реализовано.** `cloaking_rules.exit_intent` или `campaign.settings.exit_intent`: `{ "title": "Одобрение за 5 минут", "cta_text": "Оформить заявку" }` — подставляется в exit-modal.

---

## 9. Сравнительная таблица офферов

**Идея:** Таблица «Топ-3 МФО» с колонками: название, ставка, сумма, срок, CTA — повышает доверие и конверсию.

**Реализация:** `cloaking_rules.comparison` уже используется. Расширить: если есть офферы — строить таблицу по офферам, иначе — из AI-контента.

---

## 10. Визуальные CTA (крупные кнопки) ✅

**Реализовано.** LAYOUT_CSS_VARIANTS: варианты с `cta-large` (padding 1rem 2rem, font-size 1.1rem). cta_footer — sticky на mobile.

---

## Приоритеты внедрения

| # | Улучшение | Сложность | Эффект |
|---|-----------|-----------|--------|
| 1 | sub_id в affiliate URL | Низкая | Высокий (без этого postback бесполезен) |
| 2 | Клик-трекинг (click proxy) | Средняя | Высокий |
| 3 | Social proof блок | Средняя | Средний |
| 4 | Urgency блок | Низкая | Средний |
| 5 | GEO/device офферы на клиенте | Средняя | Средний |
| 6 | Настраиваемый exit-intent | Низкая | Средний |
| 7 | Второй CTA (footer) | Низкая | Низкий |
| 8 | Визуальные варианты CTA | Низкая | Низкий |

---

## Источники

- [How to Build Bridge Pages for Affiliate Marketing](https://www.keywordrush.com/blog/how-to-build-bridge-pages-for-affiliate-marketing/)
- [8 Top Affiliate Landing Page Best Practices](https://landingi.com/landing-page/affiliate-best-practices)
- [Urgency Words to Boost Conversions](https://optinmonster.com/how-to-use-urgency-to-hack-your-conversion-rate/)
- [Social Proof to Drive Conversions](https://unbounce.com/landing-pages/social-proof)
- [Sub ID and Postback in Affiliate Tracking](https://readme.anytrack.io/docs/the-subid-parameter-and-its-role-in-affiliate-tracking)
