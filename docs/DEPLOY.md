# Деплой через GitHub Actions

> **Серверы для дорвеев (VPS):** настройка Ubuntu + Nginx под хостинг статики дорвеев — в [DOORWAY_SERVER_SETUP.md](DOORWAY_SERVER_SETUP.md). Инструкция общая для всех таких серверов.

## Требуемые GitHub Secrets

| Secret | Описание |
|--------|----------|
| `DEPLOY_HOST` | IP или hostname сервера |
| `DEPLOY_USER` | SSH пользователь |
| `DEPLOY_KEY` | Приватный SSH ключ (содержимое ~/.ssh/id_rsa) |
| `DEPLOY_PATH` | Путь к клону репозитория на сервере (напр. `/opt/dorvey`) |

## Подготовка сервера

1. Установить Docker и Docker Compose.
2. Клонировать репозиторий: `git clone https://github.com/USER/dorvey.git`
3. Создать `.env` в корне проекта (рядом с `docker-compose.prod.yml`):

```env
POSTGRES_USER=dorvey
POSTGRES_PASSWORD=strong-password-here
POSTGRES_DB=dorvey
POSTGRES_PORT=5435

REDIS_PORT=6382

SECRET_KEY=your-openssl-rand-hex-32-output
APP_URL=https://your-domain.com
DEBUG=false

OPENAI_API_KEY=sk-...   # если нужна AI-генерация

# CORS (для SPA)
CORS_ORIGINS=["https://your-domain.com"]

# Celery
CELERY_BROKER_URL=redis://redis:6382/1
REDIS_URL=redis://redis:6382/0
```

4. Добавить публичный ключ GitHub Actions в `~/.ssh/authorized_keys` сервера.

5. **Первый деплой (clone по SSH):** на сервере должен быть Deploy Key для приватного репо — Settings → Deploy keys в GitHub, добавить публичный ключ из `~/.ssh/id_rsa.pub` сервера. Или использовать HTTPS-клон (тогда нужен токен).

## Порты (production)

| Сервис | Порт |
|--------|------|
| HTTP | 8085 |
| HTTPS | 8445 |
| PostgreSQL | 5435 |
| Redis | 6382 |

После `git push origin main` workflow:
1. Подключается по SSH
2. Переходит в каталог приложения, обновляет код (`git fetch` + `git reset --hard origin/main`)
3. Останавливает контейнеры **без удаления томов** (`docker compose down` без `-v`) — данные PostgreSQL в томе `postgres_data` сохраняются
4. Собирает и запускает контейнеры (`docker compose up -d --build`). При старте backend выполняет `alembic upgrade head` (только миграции, без пересоздания БД)

## SSL (HTTPS)

- Certbot/Let's Encrypt: настройте отдельно в nginx на хосте или через reverse-proxy (Traefik/Caddy).
- Файл `nginx.conf` в проекте — шаблон для проксирования на backend/frontend.

## Первый вход

При первом развёртывании автоматически создаётся администратор (если в БД нет пользователей):

- **Email:** `admin@dorvey.local` (или `DEFAULT_ADMIN_EMAIL` из .env)
- **Пароль:** `ChangeMeNow123!` (или `DEFAULT_ADMIN_PASSWORD` из .env)

Сразу после входа смени пароль (Settings или через создание нового админа и удаление дефолтного).

## Health check

- Backend: `GET /health` или `GET /api/docs`
- Frontend: корневая страница

## 502 Bad Gateway при логине

Backend не отвечает. На сервере выполни:

```bash
cd /opt/dorvey
docker compose -f docker-compose.prod.yml ps          # все ли контейнеры running?
docker compose -f docker-compose.prod.yml logs backend  # ошибки backend?
```

Частые причины:
- Нет `.env` в корне — создай по примеру выше
- Backend ещё стартует — подожди 1–2 мин (alembic + uvicorn)
- Postgres не готов — проверь логи postgres

## Откат

```bash
cd $DEPLOY_PATH
git log -1   # текущий коммит
git checkout <previous-commit-hash>
docker compose -f docker-compose.prod.yml up -d --build
```
