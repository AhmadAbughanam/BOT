# Deploying BOT on a VPS

Target layout: the repo lives at `/srv/bot`, owned by a dedicated `bot` user, with a
virtualenv at `/srv/bot/.venv` and a git-ignored `/srv/bot/.env`.

## 1. One-time setup

```bash
sudo adduser --system --group --home /srv/bot bot
sudo -u bot git clone git@github.com:AhmadAbughanam/BOT.git /srv/bot
cd /srv/bot
sudo -u bot python3.12 -m venv .venv
sudo -u bot .venv/bin/pip install -e .
sudo -u bot .venv/bin/playwright install chromium
sudo -u bot mkdir -p /srv/bot/logs
sudo -u bot cp .env.example .env      # then edit: tokens, DATABASE_URL, TELEGRAM_DEFAULT_CHAT_ID, LOG_FILE=/srv/bot/logs/bot.log
```

PostgreSQL (local) with the pgvector extension:

```bash
sudo apt install postgresql postgresql-16-pgvector
sudo -u postgres createuser bot --pwprompt
sudo -u postgres createdb bot -O bot
sudo -u bot .venv/bin/alembic upgrade head     # runs CREATE EXTENSION vector + all tables
sudo -u bot .venv/bin/python -m bot.scraping --mirror
```

## 2. API service (systemd)

```bash
sudo cp deploy/systemd/bot-api.service /etc/systemd/system/
sudo cp deploy/systemd/bot-task@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bot-api
curl -s localhost:8000/health          # {"status":"ok","db":true}
```

## 3. nginx + TLS (needed for the Telegram webhook)

```bash
sudo cp deploy/nginx/bot.conf /etc/nginx/sites-available/bot.conf
sudo ln -s /etc/nginx/sites-available/bot.conf /etc/nginx/sites-enabled/
# edit server_name, then:
sudo certbot --nginx -d bot.example.com
sudo nginx -t && sudo systemctl reload nginx

# register the webhook (uses TELEGRAM_BOT_TOKEN + TELEGRAM_WEBHOOK_SECRET from .env):
sudo -u bot .venv/bin/python scripts/set_telegram_webhook.py https://bot.example.com/telegram/webhook
```

## 4. Scheduled briefings (cron)

```bash
# regenerate the file if config/schedule.yaml changed:
sudo -u bot .venv/bin/python -m bot.scheduler crontab \
    --python /srv/bot/.venv/bin/python --workdir /srv/bot > deploy/cron/bot.cron
sudo crontab -u bot deploy/cron/bot.cron
sudo -u bot .venv/bin/python -m bot.scheduler run weather-agenda   # smoke test one task
```

## 5. Log rotation

```bash
sudo cp deploy/logrotate/bot /etc/logrotate.d/bot     # rotates whatever LOG_FILE points at
```

## 6. Instagram DM poller (optional)

```bash
sudo -u bot .venv/bin/pip install -e ".[instagram]"
# add INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD / INSTAGRAM_ALLOWED_USER_IDS to .env
sudo -u bot .venv/bin/python -m bot.channels.instagram poll    # one pass; solves any login challenge interactively
sudo cp deploy/systemd/bot-instagram.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now bot-instagram
```

## Updating

```bash
sudo -u bot /srv/bot/deploy/deploy.sh
```

Pulls, reinstalls deps, runs `alembic upgrade head`, re-mirrors the site registry, restarts `bot-api`.

## Container route (alternative)

`docker compose --profile full up -d` runs Postgres **and** an API container built from
[`Dockerfile`](../Dockerfile) (which applies migrations and mirrors the registry on start).
Cron still runs on the host, calling `docker compose exec api python -m bot.scheduler run <task>`.
