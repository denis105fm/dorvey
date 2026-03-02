#!/usr/bin/env python3
"""
Получить Refresh Token для Google Ads API (один раз, локально).

Использование:
  1. Установи зависимость: pip install google-auth-oauthlib
  2. В Google Cloud Console для OAuth-клиента добавь в "Authorized redirect URIs":
     http://127.0.0.1:8080
  3. Запусти скрипт и введи Client ID и Client Secret (те же, что в Настройках → Google Ads):
     python scripts/google_ads_refresh_token.py
  4. Откроется браузер — войди в аккаунт Google с доступом к Google Ads.
  5. Скопируй из консоли строку "Refresh token: 1//0g..." и вставь в Настройки Dorvey.
"""

import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Установи: pip install google-auth-oauthlib")
    sys.exit(1)

SCOPE = "https://www.googleapis.com/auth/adwords"
REDIRECT_URI = "http://127.0.0.1:8080/"


def main() -> None:
    print("Refresh Token для Google Ads API (Dorvey)")
    print("Client ID и Client Secret — те же, что в Настройках → Интеграции → Google Ads.\n")
    client_id = (input("Client ID: ").strip() or "").strip()
    client_secret = (input("Client Secret: ").strip() or "").strip()
    if not client_id or not client_secret:
        print("Нужны оба значения.")
        sys.exit(1)

    # Конфиг в формате "installed app" (как client_secrets.json)
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": [REDIRECT_URI.rstrip("/"), "http://127.0.0.1:8080"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=[SCOPE],
    )
    flow.redirect_uri = REDIRECT_URI

    print("\nОткроется браузер — войди в Google (аккаунт с доступом к Google Ads)...\n")
    creds = flow.run_local_server(port=8080, prompt="consent")

    if not creds.refresh_token:
        print("Refresh token не вернулся. При авторизации выбери аккаунт и дай доступ.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Refresh token (скопируй в Настройки → Интеграции → Google Ads):")
    print("=" * 60)
    print(creds.refresh_token)
    print("=" * 60)


if __name__ == "__main__":
    main()
