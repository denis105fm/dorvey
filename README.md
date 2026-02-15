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

### 3. Или полный Docker (рекомендуется)

```bash
docker-compose up -d --build
```

Сервисы: postgres, redis, backend, frontend, celery, celery-beat.

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

- **Кампании, домены, серверы** — управление, default affiliate_rules
- **8 шаблонов** — дефолт, минималистичный, финансовый, health, e-commerce, медиа, премиум, полный
- **AI-генерация** — OpenAI, пакетный режим, валидация forbidden_words
- **Деплой** — SSH/FTP, batch с паузами, SSL certbot
- **AI Optimizer** — рекомендации, авто-правки, откат, A/B winner, predict CR
- **Автоматизация** — Celery Beat: cron-run-all (3:00), auto-generate (4:30)
- **Интеграции** — Webhooks, Telegram, Slack, GSC, Bing, Voluum, Binom, Hotjar, Clarity

## Документация

- [MASTER_PLAN](docs/MASTER_PLAN.md) — план
- [TEMPLATES](docs/TEMPLATES.md) — шаблоны
- [DEPLOY](docs/DEPLOY.md) — деплой
- [CRON](docs/CRON.md) — cron и Celery Beat

## Лицензия

Private / Proprietary
