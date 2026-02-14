# Запуск Dorvey

## Docker (рекомендуется)

Запуск всего стека одной командой:

```bash
docker compose up -d --build
```

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/api/docs

Остановка: `docker compose down`

---

## Локальный запуск

**Нужно:** установленные Python 3.11+, Node.js, PostgreSQL, Redis (опционально).

### Вариант 1: Скрипты (Windows)

Открыть **два** терминала:

1. **Backend:** `run-backend.bat` — создаёт venv, ставит зависимости, миграции, запускает API
2. **Frontend:** `run-frontend.bat` — ставит npm-зависимости, запускает UI

### Вариант 2: Вручную

**Терминал 1 — Backend:**
```bash
cd backend
copy .env.example .env    # Windows
# cp .env.example .env   # Linux/Mac

py -m venv venv          # или: python3 -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Терминал 2 — Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Перед первым запуском

**Вариант A: Docker** (если Docker Desktop запущен)
```bash
docker compose up -d
```
Создаст PostgreSQL и Redis на портах 5432 и 6379.

**Вариант B: Локальный PostgreSQL**
Создай БД:
```sql
CREATE USER dorvey WITH PASSWORD 'dorvey';
CREATE DATABASE dorvey OWNER dorvey;
```

### Celery (опционально)

```bash
cd backend
venv\Scripts\activate
celery -A app.celery_app worker -l info
```

---

## Адреса

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/api/docs

---

## Регистрация

Открой http://localhost:5173 → Register → создай аккаунт → войди.
