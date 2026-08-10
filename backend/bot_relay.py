#!/usr/bin/env python3
"""
Telegram → Hermes Agent Relay (file-queue pattern)
Polls bot_queue/incoming.txt for new messages, processes them,
writes replies to bot_queue/outgoing.txt.

Configuration: reads BOT_TOKEN and ADMIN_CHAT_ID from
/home/junglee01/.hermes/.botenv or .env files.
"""
import os
import sys
import time
import json
from pathlib import Path

# Try loading .botenv
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
BOT_QUEUE = Path(__file__).with_name("bot_queue")
INCOMING = BOT_QUEUE / "incoming.txt"
OUTGOING = BOT_QUEUE / "outgoing.txt"
POLL_INTERVAL = 1.0

def ensure_queue():
    BOT_QUEUE.mkdir(exist_ok=True)
    INCOMING.touch(exist_ok=True)
    OUTGOING.touch(exist_ok=True)

def process_message(text: str) -> str:
    """Minimal agent loop: forward to backend /api/hook or return canned reply."""
    try:
        import urllib.request
        payload = json.dumps({"task": text, "source": "telegram"}).encode()
        req = urllib.request.Request(
            "http://localhost:8080/hooks",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode()[:500]
    except Exception as exc:
        return f"Agent busy/offline. Error: {exc}"

def main():
    ensure_queue()
    if not BOT_TOKEN:
        print("No BOT_TOKEN found. Queue mode active.", flush=True)
    last_seen = 0
    while True:
        try:
            data = INCOMING.read_text()
            lines = data.splitlines()
            new_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    uid, msg = line.split("|", 1)
                except ValueError:
                    continue
                key = f"{uid}:{msg}"
                if key == last_seen:
                    new_lines.append(line)
                    continue
                last_seen = key
                reply = process_message(msg)
                OUTGOING.write_text(f"{uid}|{reply}\n")
                new_lines.append(line)
            # keep unprocessed lines
            INCOMING.write_text("\n".join(new_lines) + "\n" if new_lines else "")
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("Relay stopped.", flush=True)
            sys.exit(0)
        except Exception as exc:
            print(f"Relay error: {exc}", flush=True)
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
