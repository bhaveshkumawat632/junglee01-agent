#!/usr/bin/env python3
import os, sys, json

REQUIRED = [
    "YOUTUBE_CLIENT_ID",
    "YOUTUBE_CLIENT_SECRET",
    "YOUTUBE_REFRESH_TOKEN"
]

missing = [k for k in REQUIRED if not os.getenv(k)]
if missing:
    print(json.dumps({
        "ready": False,
        "missing": missing,
        "action": "Add these as GitHub Actions secrets after YouTube OAuth authorization."
    }, indent=2))
    raise SystemExit(2)

print(json.dumps({
    "ready": True,
    "message": "YouTube OAuth secrets are present. Upload implementation can run."
}, indent=2))
