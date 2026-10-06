#!/usr/bin/env python3
"""Submit one multi-scene LTX batch to the user's free Kaggle T4x2 quota."""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
TEMPLATE=HERE/"kaggle_ltx_batch_worker.py"

def run(cmd,check=True,capture=False):
    print("+"," ".join(map(str,cmd)),flush=True)
    return subprocess.run(
        [str(x) for x in cmd],
        check=check,
        text=True,
        capture_output=capture,
    )

def probe_duration(path):
    p=run([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=nw=1:nk=1",path
    ],capture=True)
    return float(p.stdout.strip() or 0)

def fit_clip(src,dst,target):
    duration=probe_duration(src)
    if duration<=0:
        raise RuntimeError(f"Invalid generated duration for {src}")
    ratio=float(target)/duration
    run([
        "ffmpeg","-nostdin","-y","-i",src,
        "-vf",f"setpts={ratio:.8f}*PTS,fps=30,format=yuv420p",
        "-an","-t",str(target),
        "-c:v","libx264","-preset","veryfast","-crf","20",
        "-profile:v","high","-movflags","+faststart",dst,
    ])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--plan",required=True)
    ap.add_argument("--out-dir",required=True)
    ap.add_argument("--count",type=int,default=12)
    ap.add_argument("--duration",type=float,default=5.0)
    ap.add_argument("--timeout-minutes",type=int,default=80)
    ap.add_argument("--reuse-existing",action="store_true",
                    help="Reuse the latest completed Kaggle batch output without submitting a new GPU kernel")
    a=ap.parse_args()

    user=os.getenv("KAGGLE_USERNAME","").strip()
    token=os.getenv("KAGGLE_API_TOKEN","").strip()
    if not user or not token:
        raise SystemExit("KAGGLE_BATCH_CREDENTIALS_MISSING")
    if not TEMPLATE.exists():
        raise SystemExit(f"Missing Kaggle batch worker template: {TEMPLATE}")

    plan=json.loads(Path(a.plan).read_text(encoding="utf-8"))
    prompts=list(plan.get("scene_prompts") or [])
    if not prompts:
        raise SystemExit("KAGGLE_BATCH_NO_SCENE_PROMPTS")
    while len(prompts)<a.count:
        prompts.extend(list(plan.get("scene_prompts") or []))
    prompts=prompts[:a.count]

    out=Path(a.out_dir)
    out.mkdir(parents=True,exist_ok=True)
    handle=f"{user}/yvm-ltx-daily-batch"
    started=time.time()

    with tempfile.TemporaryDirectory(prefix="yvm-kaggle-batch-") as td:
        td=Path(td)
        encoded=base64.b64encode(
            json.dumps(prompts,ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        worker=TEMPLATE.read_text(encoding="utf-8")
        marker="__YVM_PROMPTS_B64__"
        if marker not in worker:
            raise SystemExit("KAGGLE_BATCH_TEMPLATE_MARKER_MISSING")
        (td/"worker.py").write_text(worker.replace(marker,encoded,1),encoding="utf-8")
        metadata={
            "id":handle,
            "title":"YVM LTX Daily Batch",
            "code_file":"worker.py",
            "language":"python",
            "kernel_type":"script",
            "is_private":True,
            "enable_gpu":True,
            "enable_internet":True,
        }
        (td/"kernel-metadata.json").write_text(json.dumps(metadata,indent=2))

        if not a.reuse_existing:
            run([
                "kaggle","kernels","push",
                "-p",td,
                "--timeout","3600",
                "--accelerator","NvidiaTeslaT4",
            ])

            deadline=time.time()+a.timeout_minutes*60
            while time.time()<deadline:
                p=run(["kaggle","kernels","status",handle],check=False,capture=True)
                status=((p.stdout or "")+"\n"+(p.stderr or "")).strip()
                print(status,flush=True)
                low=status.lower()
                if "complete" in low:
                    break
                if any(x in low for x in ("error","failed","cancel","permission","denied","forbidden","not found","cannot access","could not find")):
                    logs=run(["kaggle","kernels","logs",handle],check=False,capture=True)
                    (out/"kaggle_batch_logs.txt").write_text(
                        (logs.stdout or "")+"\n"+(logs.stderr or ""),
                        encoding="utf-8"
                    )
                    raise SystemExit("KAGGLE_BATCH_FAILED")
                time.sleep(30)
            else:
                logs=run(["kaggle","kernels","logs",handle],check=False,capture=True)
                (out/"kaggle_batch_logs.txt").write_text(
                    (logs.stdout or "")+"\n"+(logs.stderr or ""),
                    encoding="utf-8"
                )
                raise SystemExit("KAGGLE_BATCH_TIMEOUT")
        else:
            print(f"KAGGLE_BATCH_REUSE_EXISTING={handle}", flush=True)

        download=td/"output"
        download.mkdir()
        run(["kaggle","kernels","output",handle,"-p",download,"-o"])
        result_file=download/"yvm_kaggle_batch_result.json"
        if not result_file.exists():
            raise SystemExit("KAGGLE_BATCH_RESULT_MISSING")
        source_result=json.loads(result_file.read_text())

        generated=[]
        for idx in range(1,a.count+1):
            src=download/f"yvm_kaggle_scene_{idx:02d}.mp4"
            if not src.exists():
                raise SystemExit(f"KAGGLE_BATCH_SCENE_MISSING={idx}")
            dst=out/f"scene_{idx:02d}.ai.mp4"
            fit_clip(src,dst,a.duration)
            generated.append(str(dst))

        result={
            "status":"PASS",
            "provider":"kaggle_t4x2_ltxv_2b_distilled",
            "scene_count":a.count,
            "target_clip_duration":a.duration,
            "wall_seconds":round(time.time()-started,3),
            "outputs":generated,
            "source_result":source_result,
            "no_paid_api":True,
        }
        (out/"kaggle_batch_result.json").write_text(
            json.dumps(result,ensure_ascii=False,indent=2),
            encoding="utf-8"
        )
        print(json.dumps(result,ensure_ascii=False,indent=2))
        print("PROVIDER=kaggle_t4x2_ltx_batch")

if __name__=="__main__":
    main()
