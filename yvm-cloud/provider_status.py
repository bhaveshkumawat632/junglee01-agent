#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

CONFIG = json.loads(Path(__file__).with_name("config.json").read_text())

checks = {
    "agnes": bool(os.getenv("AGNES_API_KEY")),
    "hf_zerogpu": True,
    "kaggle": bool(os.getenv("KAGGLE_API_TOKEN") or (os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"))),
    "gemini_web": bool(os.getenv("GEMINI_WEB_BASE_URL") or os.getenv("GEMINI_WEB_COOKIES")),
    "google_flow": bool(os.getenv("FLOW_BRIDGE_URL") or os.getenv("FLOW_CDP_URL")),
    "youtube": all(bool(os.getenv(k)) for k in ("YOUTUBE_CLIENT_ID","YOUTUBE_CLIENT_SECRET","YOUTUBE_REFRESH_TOKEN")),
}

print("YVM CLOUD PROVIDER STATUS")
for name in CONFIG["providers"]["priority"]:
    print(f"{name}: {'CONFIGURED' if checks.get(name) else 'NOT_CONFIGURED'}")
print(f"youtube: {'CONFIGURED' if checks['youtube'] else 'NOT_CONFIGURED'}")
print("billing_details_allowed:", CONFIG["providers"]["billing_details_allowed"])
print("paid_fallback:", CONFIG["providers"]["paid_fallback"])

if CONFIG["providers"]["billing_details_allowed"] or CONFIG["providers"]["paid_fallback"]:
    print("POLICY VIOLATION")
    sys.exit(2)
