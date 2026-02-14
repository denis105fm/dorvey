@echo off
cd /d "%~dp0backend"

if not exist .env copy .env.example .env

if not exist venv (
    echo Creating venv...
    py -m venv venv 2>nul || python -m venv venv 2>nul || python3 -m venv venv
)
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt -q

echo Running migrations...
alembic upgrade head

echo Starting backend on http://localhost:8000
uvicorn app.main:app --reload --port 8000
