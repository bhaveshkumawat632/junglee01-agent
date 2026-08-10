#!/usr/bin/env python3
"""
Telegram Bot for Hermes Agent
- Bridges Telegram messages to backend /hooks endpoint
- Uses file queue for reliability
- Fast inline replies to avoid Telegram timeout
"""
import os
import sys
import json
import logging
import asyncio
from pathlib import Path

# Load .botenv
def load_botenv():
    candidates = [
        Path.home() / ".hermes" / ".botenv",
        Path.home() / ".botenv",
        Path.cwd() / ".botenv",
    ]
    for path in candidates:
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        os.environ.setdefault(key.strip(), val.strip().strip("\"'"))
            return True
    return False

load_botenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BACKEND_URL = "http://localhost:8080/hooks"
BOT_QUEUE = Path(__file__).with_name("bot_queue")
INCOMING = BOT_QUEUE / "incoming.txt"
OUTGOING = BOT_QUEUE / "outgoing.txt"
BOT_QUEUE.mkdir(exist_ok=True)
INCOMING.touch(exist_ok=True)
OUTGOING.touch(exist_ok=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Hermes Agent Relay Active\n\n"
        "Main Bhavesh ke agent se connected hoon.\n"
        "Koi bhi message ya command bhejo, main usko process karwaunga.\n\n"
        "Commands:\n"
        "/status - System status\n"
        "/help - Help\n"
        "/queue - Show pending tasks"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:8080/api/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            await update.message.reply_text(
                f"✅ Backend: {data.get('status', 'unknown')}\n"
                f"Version: {data.get('version', '?')}\n"
                f"Skills: {data.get('skills_loaded', 0)}\n"
                f"Tasks: {data.get('tasks', 0)}"
            )
    except Exception as exc:
        await update.message.reply_text(f"❌ Backend unreachable: {exc}")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        lines = INCOMING.read_text().strip().splitlines()
        count = len([l for l in lines if l.strip()])
        await update.message.reply_text(f"📊 Queue: {count} pending messages")
    except Exception:
        await update.message.reply_text("Queue check failed.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_msg = update.message.text.strip()
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"
    
    # Fast acknowledgement
    status_msg = await update.message.reply_text("⏳ Processing...")
    
    # Append to incoming queue
    entry = f"{chat_id}|{user_msg}\n"
    try:
        with open(INCOMING, "a") as f:
            f.write(entry)
    except Exception:
        await status_msg.edit_text("❌ Queue write failed.")
        return
    
    # Wait for reply in outgoing queue
    for _ in range(20):  # 20 seconds max
        try:
            content = OUTGOING.read_text()
            for line in content.strip().splitlines():
                if line.startswith(f"{chat_id}|"):
                    reply = line.split("|", 1)[1]
                    await status_msg.edit_text(reply)
                    # Clear processed line
                    remaining = [l for l in content.strip().splitlines() if not l.startswith(f"{chat_id}|")]
                    OUTGOING.write_text("\n".join(remaining) + "\n" if remaining else "")
                    return
        except Exception:
            pass
        await asyncio.sleep(1)
    
    await status_msg.edit_text("⏱️ Timeout. Agent processing...")

def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not found in .botenv", flush=True)
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("queue", queue_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Telegram bot starting...", flush=True)
    app.run_polling(drop_pending_updates=True, allowed_updates=["message"])

if __name__ == "__main__":
    main()
