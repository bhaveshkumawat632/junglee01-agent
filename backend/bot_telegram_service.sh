#!/usr/bin/env bash
set -euo pipefail
VENV="/home/junglee01/junglee01-project/backend/.relay_venv"
BOT="/home/junglee01/junglee01-project/backend/telegram_bot.py"
cd "$(dirname "$BOT")"
"$VENV/bin/python" "$BOT"
