#!/usr/bin/env python3
"""No-paid-fallback Vidu video adapter.

This adapter will ONLY use Vidu's claw_pass daily quota. It never falls back
to normal credit billing. VIDU_TOKEN must be supplied by the user as a secret.
"""
import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

def run_json(cmd):
    p=subprocess.run(cmd,text=True,capture_output=True)
    out=(p.stdout or "").strip()
    if p.returncode != 0:
        raise RuntimeError((out+"\n"+(p.stderr or "")).strip())
    # vidu-cli prints one JSON object.
    for line in reversed(out.splitlines()):
        line=line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise RuntimeError("vidu-cli returned no JSON: "+out[-1000:])

def ffprobe_ok(path: Path):
    p=subprocess.run([
        "ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","stream=codec_name,width,height",
        "-show_entries","format=duration",
        "-of","json",str(path)
    ],text=True,capture_output=True)
    if p.returncode:
        return False, {}
    d=json.loads(p.stdout)
    s=(d.get("streams") or [{}])[0]
    f=d.get("format") or {}
    ok=bool(s.get("codec_name")) and int(s.get("height",0)) > int(s.get("width",0)) and float(f.get("duration",0)) >= 1
    return ok,d

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prompt",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--duration",type=int,default=8)
    ap.add_argument("--model-version",default="3.2")
    ap.add_argument("--poll-seconds",type=int,default=10)
    ap.add_argument("--timeout-seconds",type=int,default=1800)
    ap.add_argument("--quota-only",action="store_true")
    a=ap.parse_args()

    if not os.getenv("VIDU_TOKEN"):
        raise SystemExit("VIDU_TOKEN is not configured")
    os.environ.setdefault("VIDU_BASE_URL","https://service.vidu.com")

    cli=shutil.which("vidu-cli")
    if not cli:
        raise SystemExit("vidu-cli is not installed")

    quota=run_json([cli,"quota","pass"])
    if not quota.get("ok") or not quota.get("has_pass"):
        raise SystemExit("VIDU_CLAW_PASS_UNAVAILABLE="+json.dumps(quota,separators=(",",":")))
    remain=int(quota.get("remain_seconds") or 0)
    print("VIDU_CLAW_PASS_REMAIN_SECONDS="+str(remain),flush=True)
    if a.quota_only:
        return
    if remain < a.duration:
        raise SystemExit(f"VIDU_CLAW_PASS_INSUFFICIENT remain={remain} need={a.duration}")

    submit=run_json([
        cli,"task","submit",
        "--type","text2video",
        "--prompt",a.prompt,
        "--duration",str(a.duration),
        "--model-version",a.model_version,
        "--resolution","1080p",
        "--aspect-ratio","9:16",
        "--codec","h264",
        "--sample-count","1",
        "--schedule-mode","claw_pass",
    ])
    task_id=str(submit.get("task_id") or "")
    if not task_id:
        raise SystemExit("VIDU_NO_TASK_ID="+json.dumps(submit,separators=(",",":")))
    print("VIDU_TASK_ID="+task_id,flush=True)

    out=Path(a.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    deadline=time.time()+a.timeout_seconds
    last={}
    while time.time()<deadline:
        last=run_json([cli,"task","get",task_id])
        state=str(last.get("state") or "").lower()
        print("VIDU_STATE="+state,flush=True)
        if state=="success":
            got=run_json([cli,"task","get",task_id,"--output",str(out)])
            files=got.get("downloaded_files") or []
            # When --output is a file path, the CLI writes directly there.
            if not out.exists() and files:
                candidate=Path(files[0])
                if candidate.exists():
                    candidate.replace(out)
            if not out.exists():
                raise SystemExit("VIDU_SUCCESS_BUT_OUTPUT_MISSING="+json.dumps(got,separators=(",",":")))
            ok,probe=ffprobe_ok(out)
            if not ok:
                out.unlink(missing_ok=True)
                raise SystemExit("VIDU_OUTPUT_QC_FAIL="+json.dumps(probe,separators=(",",":")))
            print("VIDU_OUTPUT="+str(out),flush=True)
            print("VIDU_PROVIDER=claw_pass",flush=True)
            return
        if state=="failed":
            raise SystemExit("VIDU_TASK_FAILED="+json.dumps(last,separators=(",",":")))
        time.sleep(a.poll_seconds)
    raise SystemExit("VIDU_TASK_TIMEOUT="+json.dumps(last,separators=(",",":")))

if __name__=="__main__":
    main()
