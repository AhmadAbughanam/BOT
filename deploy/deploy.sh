#!/usr/bin/env bash
# Pull latest, update deps + schema + site registry, restart the API.
# Run as the `bot` user from /srv/bot:  ./deploy/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."

git pull --ff-only
.venv/bin/pip install -e . -q
.venv/bin/playwright install chromium
.venv/bin/alembic upgrade head
.venv/bin/python -m bot.scraping --mirror

sudo systemctl restart bot-api
sudo systemctl --no-pager status bot-api | head -n 5

echo "deployed $(git rev-parse --short HEAD)"
