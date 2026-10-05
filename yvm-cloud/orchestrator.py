#!/usr/bin/env python3
import json, os, sys, subprocess, pathlib, time

ROOT = pathlib.Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text())
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

PROVIDERS = CFG["provider_order"]

def env_ok(name):
    return bool(os.getenv(name))

def provider_ready(p):
    checks = {
        "agnes": ["AGNES_API_KEY"],
        "kaggle": ["KAGGLE_USERNAME", "KAGGLE_KEY"],
        "gemini_web": ["GEMINI_WEB_COOKIE"],
        "google_flow": ["FLOW_CDP_URL"],
        "hf_zerogpu": [],
    }
    missing = [k for k in checks[p] if not env_ok(k)]
    return len(missing) == 0, missing

def choose_provider():
    report = []
    for p in PROVIDERS:
        ok, missing = provider_ready(p)
        report.append({"provider": p, "ready": ok, "missing": missing})
        if ok:
            return p, report
    return None, report

def main():
    provider, report = choose_provider()
    (OUT / "provider-readiness.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if not provider:
        print("NO_PROVIDER_READY")
        return 3
    print("SELECTED_PROVIDER=" + provider)
    print("Provider generation adapter will run only after that provider passes the separate 4x burn-in.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
