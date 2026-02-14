# Деплой через GitHub Actions

## Требуемые GitHub Secrets

| Secret | Описание |
|--------|----------|
| `DEPLOY_HOST` | IP или hostname сервера |
| `DEPLOY_USER` | SSH пользователь |
| `SSH_PRIVATE_KEY` | Приватный SSH ключ (содержимое ~/.ssh/id_rsa) |
| `DEPLOY_PATH` | Путь к клону репозитория на сервере (напр. `/home/user/dorvey`) |

## Подготовка сервера

1. Установить Docker и Docker Compose
2. Клонировать репозиторий: `git clone https://github.com/USER/dorvey.git`
3. Создать `.env` с переменными (POSTGRES_PASSWORD, SECRET_KEY, APP_URL и т.д.)
4. Добавить публичный ключ GitHub Actions в `~/.ssh/authorized_keys` сервера

## Порт

После `git push origin main` workflow деплоит на сервер. Приложение доступно на портах **8080** (HTTP) и **8443** (HTTPS).
