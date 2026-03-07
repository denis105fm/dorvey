# Настройка сервера для дорвеев (VPS)

Инструкция одинакова для любого нового VPS под хостинг дорвеев: Ubuntu, Nginx, каталог для деплоя из Dorvey. После добавления сервера в Dorvey подключаешься по SSH (PuTTY или терминал) и выполняешь команды ниже.

---

## 1. ОС

Рекомендуется **Ubuntu 24.04 LTS** или **22.04 LTS** (поддержка долгая, пакеты актуальные).

---

## 2. Подключение по SSH (PuTTY)

- Хост: IP или hostname сервера.
- Порт: 22.
- Логин/пароль или ключ — как выдали при создании VPS.

Того же пользователя и ключ/пароль указываешь в Dorvey в настройках сервера.

---

## 3. Команды на сервере (вставить по порядку)

### Обновление и Nginx

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y nginx
```

### Каталог для сайтов и права

Путь по умолчанию в Dorvey — `/var/www/html`. Пользователь, под которым заходишь по SSH, должен иметь право писать в этот каталог.

```bash
sudo mkdir -p /var/www/html
sudo chown -R $USER:$USER /var/www/html
```

Если в Dorvey будешь использовать отдельного пользователя (например `deploy`), создай его и выдай ему каталог:

```bash
# sudo useradd -m -s /bin/bash deploy
# sudo mkdir -p /var/www/html && sudo chown -R deploy:deploy /var/www/html
```

### Включить и запустить Nginx

```bash
sudo systemctl enable nginx
sudo systemctl start nginx
sudo systemctl status nginx
```

В выводе `status` должно быть `active (running)`.

### Файрвол (рекомендуется)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
sudo ufw status
```

---

## 4. Настройки в Dorvey

В разделе **Серверы** укажи:

- **Хост** — IP или hostname.
- **Порт** — 22 (если не менял на VPS).
- **Пользователь** — тот, под которым заходишь по SSH (например `root` или `deploy`).
- **Путь к сайту** — ` /var/www/html` (можно не менять).
- **Авторизация** — пароль или SSH-ключ. Если ключ: вставь **приватный** ключ целиком (блок от `-----BEGIN ... KEY-----` до `-----END ... KEY-----`).

Проверь подключение кнопкой проверки в Dorvey, затем сделай тестовый деплой одного дорвея.

---

## 5. Клоака (бот vs человек)

Когда домен добавлен и дорвеи задеплоены, чтобы боты получали `index.seo.html`, а люди — `index.html`, настрой Nginx по шаблону в проекте:

- Файл: **`docs/nginx-cloaking.conf`** в репозитории.
- Скопируй оттуда `map $http_user_agent` и блок `server` (или включи файл в конфиг домена).
- В `server` укажи свой `server_name` и при необходимости `root` (если используешь не `/var/www/html`).
- Перезагрузи конфиг: `sudo nginx -t && sudo systemctl reload nginx`.

Подробнее про клоаку — в **`docs/BLACK_DOORWAYS.md`** и **`docs/CLOAKING_AND_KEYWORDS_PLAN.md`**.

---

## Итого

| Шаг | Действие |
|-----|----------|
| 1 | Ubuntu 24.04 или 22.04 |
| 2 | Подключиться по SSH (PuTTY), тот же пользователь/ключ — в Dorvey |
| 3 | `apt update && apt upgrade -y`, `apt install -y nginx` |
| 4 | `mkdir -p /var/www/html`, `chown -R $USER:$USER /var/www/html` |
| 5 | `systemctl enable nginx && systemctl start nginx` |
| 6 | `ufw allow OpenSSH` + `ufw allow 'Nginx Full'` + `ufw enable` |
| 7 | В Dorvey: хост, пользователь, путь `/var/www/html`, пароль или ключ |
| 8 | Для клоаки — конфиг из `docs/nginx-cloaking.conf` на сервере |

Одни и те же шаги подходят для всех серверов дорвеев (и для чёрных, и для обычных).
