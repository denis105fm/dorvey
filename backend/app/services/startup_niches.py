"""Startup niches reference for keyword discovery."""

# Справочник ниш/микрониш для стартового набора ключей (seed-фразы для провайдера)
STARTUP_NICHES = [
    {"id": "loans", "name": "Займы и кредиты", "seeds": ["займ на карту", "кредит наличными", "микрозайм"]},
    {"id": "insurance", "name": "Страхование", "seeds": ["страховка авто", "ОСАГО", "каско"]},
    {"id": "gambling", "name": "Букмекеры и казино", "seeds": ["ставки на спорт", "букмекер", "казино онлайн"]},
    {"id": "crypto", "name": "Криптовалюты", "seeds": ["биткоин", "криптовалюта", "обменник"]},
    {"id": "dating", "name": "Знакомства", "seeds": ["знакомства онлайн", " dating", "отношения"]},
    {"id": "education", "name": "Образование", "seeds": ["курсы онлайн", "обучение", "репетитор"]},
    {"id": "health", "name": "Здоровье", "seeds": ["лечение", "клиника", "врач"]},
    {"id": "beauty", "name": "Красота", "seeds": ["косметика", "уход за кожей", "салон"]},
    {"id": "travel", "name": "Путешествия", "seeds": ["туры", "авиабилеты", "отели"]},
    {"id": "finance", "name": "Финансы", "seeds": ["инвестиции", "брокер", "трейдинг"]},
]

# Рекомендуемые seed-фразы по типу кампании (English). Порядок важен.
CAMPAIGN_SEED_SUGGESTIONS = [
    {"id": "click_box", "keywords": ["click box", "clickbox"], "label": "Click Box", "seeds": ["clicker game", "idle game", "click games", "incremental game", "tap game"]},
    {"id": "clicker", "keywords": ["clicker", "click"], "label": "Clicker / Casual", "seeds": ["clicker game", "idle game", "casual game", "click games", "incremental game"]},
    {"id": "survey", "keywords": ["survey", "surveys"], "label": "Survey", "seeds": ["paid survey", "online survey", "survey rewards", "get paid for surveys", "survey sites"]},
    {"id": "social_video", "keywords": ["social network", "social survey", "video"], "label": "Social / Video", "seeds": ["video survey", "social media survey", "online survey", "paid survey"]},
    {"id": "survey_mix", "keywords": ["mixer", "mix"], "label": "Survey Mix", "seeds": ["paid survey", "online survey", "survey rewards", "survey sites"]},
    {"id": "casual", "keywords": ["casual"], "label": "Casual", "seeds": ["casual game", "idle game", "clicker game", "mobile casual game", "free casual games"]},
]

# Готовые списки ключей для импорта CSV (English). Один список на тип кампании.
CAMPAIGN_KEYWORDS_CSV: dict[str, list[str]] = {
    "click_box": [
        "clicker game", "idle game", "click games", "incremental game", "tap game",
        "best clicker games", "clicker games online", "idle clicker", "cookie clicker",
        "clicker game unblocked", "free clicker games", "mobile clicker game",
        "idle games", "incremental games", "tap games", "clicker games 2024",
        "casual clicker game", "tycoon clicker", "clicker game download",
        "online clicker games", "clicker game app", "idle miner", "idle games online",
    ],
    "clicker": [
        "clicker game", "idle game", "casual game", "click games", "incremental game",
        "best clicker games", "idle clicker", "casual clicker", "free clicker games",
        "clicker games online", "mobile clicker game", "cookie clicker",
        "idle games", "incremental games", "tap game", "casual games",
        "clicker game unblocked", "tycoon game", "idle games online",
        "clicker game app", "casual games online", "best idle games",
    ],
    "survey": [
        "paid survey", "online survey", "survey rewards", "get paid for surveys",
        "survey sites", "paid online surveys", "survey panel", "market research survey",
        "take surveys for money", "best survey sites", "survey app",
        "paid surveys online", "earn money surveys", "survey rewards app",
        "online paid surveys", "survey junkie", "swagbucks surveys",
        "survey sites that pay", "get paid to take surveys", "survey company",
    ],
    "social_video": [
        "video survey", "social media survey", "online survey", "paid survey",
        "video survey rewards", "social survey app", "get paid for video survey",
        "online video survey", "paid video survey", "survey rewards",
        "social media paid survey", "video opinion survey", "survey sites",
    ],
    "survey_mix": [
        "paid survey", "online survey", "survey rewards", "survey sites",
        "get paid for surveys", "paid online surveys", "survey panel",
        "take surveys for money", "best survey sites", "survey app",
        "market research survey", "earn money surveys", "survey junkie",
    ],
    "casual": [
        "casual game", "idle game", "clicker game", "mobile casual game",
        "free casual games", "casual games online", "best casual games",
        "casual mobile games", "idle clicker", "incremental game",
        "tap game", "casual game download", "relaxing casual games",
        "casual puzzle game", "casual games 2024", "top casual games",
    ],
}


def get_suggested_seeds_for_campaign_name(campaign_name: str) -> tuple[list[str], str | None, str | None]:
    """По названию кампании возвращает (seeds, label, type_id для CSV)."""
    if not (campaign_name or "").strip():
        return [], None, None
    name_lower = campaign_name.strip().lower()
    for rule in CAMPAIGN_SEED_SUGGESTIONS:
        for kw in rule["keywords"]:
            if kw in name_lower:
                return list(rule["seeds"]), rule.get("label"), rule.get("id")
    return [], None, None


def get_campaign_export_type_for_name(campaign_name: str) -> str | None:
    """Возвращает id типа для экспорта CSV (click_box, survey, ...) или None."""
    if not (campaign_name or "").strip():
        return None
    name_lower = campaign_name.strip().lower()
    for rule in CAMPAIGN_SEED_SUGGESTIONS:
        for kw in rule["keywords"]:
            if kw in name_lower:
                return rule.get("id")
    return None
