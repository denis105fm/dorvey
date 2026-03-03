#!/usr/bin/env python3
"""
Скрипт для проверки запроса ключей к Google Ads API из командной строки.
Учётные данные берутся из переменных окружения (не хранятся в коде).

Запуск из корня backend:
  python scripts/fetch_google_ads_keywords_cli.py

Или с переменными в одной строке (подставьте свои значения):
  set GOOGLE_ADS_DEVELOPER_TOKEN=ваш_токен
  set GOOGLE_ADS_CLIENT_ID=xxx.apps.googleusercontent.com
  set GOOGLE_ADS_CLIENT_SECRET=GOCSPX-...
  set GOOGLE_ADS_REFRESH_TOKEN=1//...
  set GOOGLE_ADS_CUSTOMER_ID=403-443-4560
  set GOOGLE_ADS_MANAGER_CUSTOMER_ID=185-780-6498
  python scripts/fetch_google_ads_keywords_cli.py
"""
import asyncio
import os
import sys

# Добавляем корень backend в path для импорта app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    dev = (os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN") or "").strip()
    client_id = (os.environ.get("GOOGLE_ADS_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("GOOGLE_ADS_CLIENT_SECRET") or "").strip()
    refresh_token = (os.environ.get("GOOGLE_ADS_REFRESH_TOKEN") or "").strip()
    customer_id = (os.environ.get("GOOGLE_ADS_CUSTOMER_ID") or "").strip() or None
    manager_customer_id = (os.environ.get("GOOGLE_ADS_MANAGER_CUSTOMER_ID") or "").strip() or None

    if not all([dev, client_id, client_secret, refresh_token]):
        print("Задайте переменные окружения:")
        print("  GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_REFRESH_TOKEN")
        print("Опционально: GOOGLE_ADS_CUSTOMER_ID, GOOGLE_ADS_MANAGER_CUSTOMER_ID (для тестового MCC)")
        sys.exit(1)

    print("Параметры:")
    print("  Developer Token: ...", dev[-6:] if len(dev) > 6 else "(не задан)")
    print("  Client ID:", client_id[:50] + "..." if len(client_id) > 50 else client_id)
    print("  Customer ID:", customer_id or "(не задан — будет первый из списка)")
    print("  Manager ID (MCC):", manager_customer_id or "(не задан)")
    print()

    from app.services.google_ads_keywords_service import fetch_keywords_for_keywords

    print("Запрос идей ключей (seed=займ, country=US, limit=10)...")
    try:
        keywords, debug = await fetch_keywords_for_keywords(
            dev,
            client_id,
            client_secret,
            refresh_token,
            seed="займ",
            country="US",
            limit=10,
            customer_id=customer_id,
            manager_customer_id=manager_customer_id,
        )
        if debug and debug.get("message"):
            print("Ответ (подсказка/ошибка):", debug["message"])
        if debug and debug.get("api_error"):
            print("API error (сырой):", debug["api_error"][:800])
        if debug and len(debug) > 0:
            print("Debug (полностью):", debug)
        if keywords:
            print(f"Получено ключей: {len(keywords)}")
            for i, kw in enumerate(keywords[:10], 1):
                print(f"  {i}. {kw.get('keyword')} — объём {kw.get('volume')}, CPC {kw.get('cpc')}")
        else:
            print("Ключей не получено.")
    except Exception as e:
        print("Исключение:", type(e).__name__)
        print("Текст:", str(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
