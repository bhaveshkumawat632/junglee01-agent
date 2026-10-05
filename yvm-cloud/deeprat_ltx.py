#!/usr/bin/env python3
import argparse, os, shutil, subprocess
from pathlib import Path
from gradio_client import Client

SPACE=os.getenv("HF_DEEPRAT_SPACE","DeepRat/LTX-Video-ZeroGPU-Optimized")

def find_video(x):
    candidates=[]
    def walk(v):
        if isinstance(v,str): candidates.append(v)
        elif isinstance(v,dict):
            for z in v.values(): walk(z)
        elif isinstance(v,(list,tuple)):
            for z in v: walk(z)
    walk(x)
    for p in candidates:
        if p and os.path.exists(p) and p.lower().endswith((".mp4",".webm",".mov")):
            return p
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prompt",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--duration",type=float,default=3.0)
    ap.add_argument("--seed",type=int,default=42)
    a=ap.parse_args()
    c=Client(SPACE,verbose=False)
    result=c.predict(
        a.prompt,
        "worst quality, inconsistent motion, blurry, jittery, distorted, deformed anatomy, text, watermark, logo",
        None,
        None,
        768,
        448,
        "text-to-video",
        a.duration,
        9,
        a.seed,
        False,
        1.0,
        False,
        False,
        api_name="/text_to_video",
    )
    print("RESULT",result)
    p=find_video(result)
    if not p:
        raise SystemExit("No video file returned")
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,out)
    q=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=codec_name","-of","csv=p=0",str(out)],capture_output=True,text=True)
    if q.returncode!=0 or not q.stdout.strip():
        raise SystemExit("Returned object is not a valid video")
    print(out)

if __name__=="__main__":
    main()
