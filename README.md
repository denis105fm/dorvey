# Dorvey — Система умных дорвеев

Платформа для автоматизированного создания, деплоя и AI-оптимизации дорвеев.

## Стек

- **Backend:** Python, FastAPI, PostgreSQL, Redis, Celery
- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **AI:** OpenAI API
- **Деплой:** Docker Compose

## Быстрый старт

### 1. Клонировать и настроить

```bash
cd dorvey
cp backend/.env.example backend/.env
# Отредактируйте backend/.env (SECRET_KEY, OPENAI_API_KEY и т.д.)
```

### 2. Запуск через Docker

```bash
docker-compose up -d postgres redis
# Подождите, пока PostgreSQL будет готов

# Миграции (из хоста, с установленным Python)
cd backend
pip install -r requirements.txt
alembic upgrade head

# Запуск backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# В другом терминале — frontend
cd frontend
npm install
npm run dev
```

### 3. Или полный Docker

```bash
docker-compose up -d
```

После запуска:
- Frontend: http://localhost:5173 (или 80 в production)
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs

### 4. Регистрация

Откройте http://localhost:5173, перейдите в «Регистрация» и создайте аккаунт.

## Структура проекта

```
dorvey/
├── backend/          # FastAPI приложение
│   ├── app/
│   │   ├── api/      # Роутеры
│   │   ├── core/     # Конфиг, БД, security
│   │   ├── models/   # SQLAlchemy модели
│   │   └── schemas/  # Pydantic схемы
│   └── alembic/      # Миграции
├── frontend/         # React SPA
├── docs/
│   └── MASTER_PLAN.md   # Полный план разработки
└── docker-compose.yml
```

## Функции

- **Кампании, домены, серверы** — управление инфраструктурой
- **AI-генерация** — OpenAI для контента дорвеев
- **Пакетная генерация** — несколько ключей за раз
- **Деплой** — SSH на сервер
- **Postback** — приём конверсий (sub_id=doorway_id)
- **Аналитика** — показы, клики, конверсии, выручка
- **AI Optimizer** — рекомендации, откат при падении CR
- **Webhooks** — уведомления при deploy, conversion, rollback
- **Cron auto-rollback** — POST /api/cron/auto-rollback
- **Offers** — несколько офферов с geo/device

## Roadmap

См. [docs/MASTER_PLAN.md](docs/MASTER_PLAN.md) — все фазы реализованы.

## Лицензия

Private / Proprietary
