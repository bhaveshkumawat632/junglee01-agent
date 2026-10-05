#!/usr/bin/env python3
"""Kaggle T4x2 benchmark worker for LTX-Video 2B distilled.

Runs entirely inside a Kaggle GPU notebook/script. It does not use paid APIs.
The script creates one vertical motion clip and writes machine-readable metrics
next to the output so GitHub Actions can calculate practical capacity.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

WORK=Path("/kaggle/working")
SRC=WORK/"LTX-Video"
OUTDIR=WORK/"ltx_out"
RESULT=WORK/"yvm_kaggle_result.json"
FINAL=WORK/"yvm_kaggle_clip.mp4"

PROMPT=os.getenv(
    "YVM_PROMPT",
    "A cinematic documentary shot on a 1990s Wall Street trading floor. "
    "Adult professional traders move quickly between desks filled with CRT monitors, "
    "phones and printed market sheets. The camera slowly pushes forward through the "
    "busy room while people gesture and exchange information. Authentic period office "
    "lighting, realistic human motion, financial newsroom atmosphere, no logos, "
    "no readable text, no watermark, vertical composition."
)

def run(cmd, cwd=None):
    print("+"," ".join(map(str,cmd)),flush=True)
    subprocess.run([str(x) for x in cmd],cwd=cwd,check=True)

def main():
    started=time.time()
    gpu=subprocess.run(["nvidia-smi","--query-gpu=name,memory.total","--format=csv,noheader"],
                       text=True,capture_output=True)
    if gpu.returncode:
        raise SystemExit("KAGGLE_GPU_NOT_AVAILABLE")
    print("GPUS=\n"+gpu.stdout,flush=True)

    if not SRC.exists():
        run(["git","clone","--depth","1","https://github.com/Lightricks/LTX-Video.git",SRC])

    # Official inference dependencies.
    run([sys.executable,"-m","pip","install","-q","-e",".[inference]"],cwd=SRC)

    cfg=SRC/"configs/ltxv-2b-0.9.6-distilled.yaml"
    text=cfg.read_text()
    text=text.replace("prompt_enhancement_words_threshold: 120",
                      "prompt_enhancement_words_threshold: 0")
    cfg.write_text(text)

    OUTDIR.mkdir(parents=True,exist_ok=True)
    gen_started=time.time()
    run([
        sys.executable,"inference.py",
        "--prompt",PROMPT,
        "--height","768",
        "--width","448",
        "--num_frames","121",
        "--frame_rate","30",
        "--seed","632",
        "--pipeline_config","configs/ltxv-2b-0.9.6-distilled.yaml",
        "--output_path",str(OUTDIR),
    ],cwd=SRC)
    generation_seconds=time.time()-gen_started

    clips=sorted(OUTDIR.glob("*.mp4"),key=lambda p:p.stat().st_mtime)
    if not clips:
        raise SystemExit("KAGGLE_LTX_NO_OUTPUT")
    shutil.copy2(clips[-1],FINAL)

    probe=subprocess.run([
        "ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","stream=codec_name,width,height,r_frame_rate",
        "-show_entries","format=duration,size","-of","json",str(FINAL)
    ],text=True,capture_output=True,check=True)
    meta=json.loads(probe.stdout)
    stream=(meta.get("streams") or [{}])[0]
    fmt=meta.get("format") or {}
    duration=float(fmt.get("duration",0))
    if not stream.get("codec_name") or int(stream.get("height",0)) <= int(stream.get("width",0)) or duration < 3:
        raise SystemExit("KAGGLE_LTX_QC_FAIL="+json.dumps(meta,separators=(",",":")))

    result={
        "status":"PASS",
        "provider":"kaggle_t4x2_ltxv_2b_distilled",
        "model":"ltxv-2b-0.9.6-distilled",
        "generation_seconds":round(generation_seconds,3),
        "total_seconds":round(time.time()-started,3),
        "output_duration_seconds":duration,
        "width":int(stream.get("width",0)),
        "height":int(stream.get("height",0)),
        "output":str(FINAL),
        "no_paid_api":True,
    }
    RESULT.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=="__main__":
    main()
