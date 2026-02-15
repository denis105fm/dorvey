# Деплой через GitHub Actions

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

## Порты (production)

| Сервис | Порт |
|--------|------|
| HTTP | 8085 |
| HTTPS | 8445 |
| PostgreSQL | 5435 |
| Redis | 6382 |

После `git push origin main` workflow:
1. Подключается по SSH
2. Переходит в `DEPLOY_PATH`
3. Выполняет `git pull`, `docker compose -f docker-compose.prod.yml up -d --build`

## SSL (HTTPS)

- Certbot/Let's Encrypt: настройте отдельно в nginx на хосте или через reverse-proxy (Traefik/Caddy).
- Файл `nginx.conf` в проекте — шаблон для проксирования на backend/frontend.

## Health check

- Backend: `GET /health` или `GET /api/docs`
- Frontend: корневая страница

## Откат

```bash
cd $DEPLOY_PATH
git log -1   # текущий коммит
git checkout <previous-commit-hash>
docker compose -f docker-compose.prod.yml up -d --build
```
