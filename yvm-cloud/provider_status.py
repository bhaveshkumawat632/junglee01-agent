#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/"config.json").read_text())

checks={
    "agnes": bool(os.getenv("AGNES_API_KEY")),
    "kaggle": bool(os.getenv("KAGGLE_API_TOKEN") or (os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"))),
    "gemini_web": bool(os.getenv("GEMINI_WEB_BASE_URL") or os.getenv("GEMINI_WEB_COOKIES") or os.getenv("GEMINI_WEB_COOKIE")),
    "google_flow": bool(os.getenv("FLOW_BRIDGE_URL") or os.getenv("FLOW_CDP_URL")),
    "hf_zerogpu": True,
    "keyless_baseline": True,
    "youtube": all(bool(os.getenv(k)) for k in ("YOUTUBE_CLIENT_ID","YOUTUBE_CLIENT_SECRET","YOUTUBE_REFRESH_TOKEN")),
}

print("YVM CLOUD PROVIDER STATUS")
for name in CONFIG["provider_order"]:
    print(f"{name}: {'CONFIGURED' if checks.get(name) else 'OPTIONAL_NOT_CONFIGURED'}")
print("keyless_baseline: CONFIGURED")
print(f"youtube: {'CONFIGURED' if checks['youtube'] else 'WAITING_FOR_OAUTH'}")
print("billing_details_allowed:", CONFIG["capacity_policy"]["billing_details_allowed"])
print("paid_fallback:", CONFIG["capacity_policy"]["paid_fallback"])
print("required_multiple:", CONFIG["capacity_policy"]["required_multiple"])

if CONFIG["capacity_policy"]["billing_details_allowed"] or CONFIG["capacity_policy"]["paid_fallback"]:
    print("POLICY_VIOLATION")
    sys.exit(2)
if CONFIG["capacity_policy"]["required_multiple"] < 4:
    print("CAPACITY_POLICY_VIOLATION")
    sys.exit(3)
print("POLICY_STATUS=PASS")
