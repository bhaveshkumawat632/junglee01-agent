#!/usr/bin/env python3
import json, os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/"config.json").read_text())
METRICS_PATH=ROOT/"provider-metrics.json"
METRICS=json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else {}

def env_ok(name):
    return bool(os.getenv(name))

def high_level_readiness():
    return [
        {"provider":"agnes","configured":env_ok("AGNES_API_KEY"),"role":"optional_motion"},
        {"provider":"kaggle","configured":bool(env_ok("KAGGLE_API_TOKEN") or (env_ok("KAGGLE_USERNAME") and env_ok("KAGGLE_KEY"))),"role":"optional_gpu"},
        {"provider":"gemini_web","configured":bool(env_ok("GEMINI_WEB_BASE_URL") or env_ok("GEMINI_WEB_COOKIES") or env_ok("GEMINI_WEB_COOKIE")),"role":"optional_session"},
        {"provider":"google_flow","configured":bool(env_ok("FLOW_BRIDGE_URL") or env_ok("FLOW_CDP_URL")),"role":"optional_session"},
        {"provider":"hf_zerogpu","configured":True,"role":"keyless_motion_pool"},
        {"provider":"keyless_baseline","configured":True,"role":"guaranteed_daily_path"},
    ]

def choose_motion_lane(reference_available=False):
    if env_ok("AGNES_API_KEY"):
        return "agnes"
    motion=(METRICS.get("motion_lanes") or {})
    if (motion.get("hf_wan21_base") or {}).get("live_generation")=="pass":
        return "hf_wan21_base"
    if reference_available and (motion.get("hf_wan22_i2v") or {}).get("live_generation")=="pass":
        return "hf_wan22_i2v"
    if (motion.get("hf_ltx_zerogpu") or {}).get("live_generation")=="pass":
        return "hf_ltx_zerogpu"
    return None

def main():
    report={
        "policy":{
            "required_capacity_multiple":CFG["capacity_policy"]["required_multiple"],
            "paid_fallback":CFG["capacity_policy"]["paid_fallback"],
            "billing_details_allowed":CFG["capacity_policy"]["billing_details_allowed"],
        },
        "baseline_4x":(METRICS.get("baseline") or {}).get("four_complete_daily_cycles"),
        "providers":high_level_readiness(),
        "selected_motion_lane":choose_motion_lane(reference_available=True),
        "youtube_oauth_configured":all(env_ok(k) for k in ("YOUTUBE_CLIENT_ID","YOUTUBE_CLIENT_SECRET","YOUTUBE_REFRESH_TOKEN")),
    }
    out=ROOT/"out"
    out.mkdir(exist_ok=True)
    (out/"provider-readiness.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    if report["policy"]["paid_fallback"] or report["policy"]["billing_details_allowed"]:
        raise SystemExit(2)
    if report["baseline_4x"]!="pass":
        raise SystemExit(3)
    if not report["selected_motion_lane"]:
        print("MOTION_LANE=BASELINE_ONLY")
    else:
        print("MOTION_LANE="+report["selected_motion_lane"])
    print("ORCHESTRATOR_PREFLIGHT=PASS")

if __name__=="__main__":
    main()
