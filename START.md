# Запуск Dorvey

## Docker (рекомендуется)

```bash
docker compose up -d --build
```

Сервисы: postgres (5432), redis (6379), backend (8000), frontend (5173), celery worker, celery-beat.

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/api/docs

Остановка: `docker compose down`

## Prod

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Порты: 8085 (HTTP), 8445 (HTTPS), 5435 (Postgres), 6382 (Redis).

## Локальный запуск

**Вариант 1 — Скрипты (Windows):**
- `run-backend.bat` — backend
- `run-frontend.bat` — frontend

**Вариант 2 — Вручную:**
```bash
# Терминал 1
cd backend && cp .env.example .env
py -m venv venv && venv\Scripts\activate
pip install -r requirements.txt && alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Терминал 2
cd frontend && npm install && npm run dev
```

**PostgreSQL/Redis:** Docker `postgres redis` или локальная установка.

**Celery (batch deploy, auto-generate):**
```bash
celery -A app.celery_app worker -l info
celery -A app.celery_app beat -l info
```

## Регистрация

http://localhost:5173 → Register → войди. Первый пользователь получает роль admin.
