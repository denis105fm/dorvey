@echo off
cd /d "%~dp0frontend"

echo Installing dependencies...
call npm install

echo Starting frontend on http://localhost:5173
call npm run dev
