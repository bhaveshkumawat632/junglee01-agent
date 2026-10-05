#!/usr/bin/env python3
import argparse, os, shutil
from pathlib import Path
from gradio_client import Client, handle_file

SPACE=os.getenv("HF_VIDEO_SPACE","zai-org/CogVideoX-5B-Space")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prompt",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--image")
    ap.add_argument("--seed",type=int,default=-1)
    ap.add_argument("--scale",action="store_true")
    ap.add_argument("--rife",action="store_true")
    a=ap.parse_args()

    c=Client(SPACE,verbose=False)
    image_input=handle_file(a.image) if a.image else None
    result=c.predict(
        a.prompt,
        image_input,
        None,
        0.8,
        a.seed,
        a.scale,
        a.rife,
        api_name="/generate",
    )

    candidates=[]
    def walk(x):
        if isinstance(x,str): candidates.append(x)
        elif isinstance(x,dict):
            for v in x.values(): walk(v)
        elif isinstance(x,(list,tuple)):
            for v in x: walk(v)
    walk(result)

    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    for p in candidates:
        if p and os.path.exists(p) and p.lower().endswith((".mp4",".webm",".mov")):
            shutil.copy2(p,out)
            print(out)
            return
    raise SystemExit(f"No video file returned by {SPACE}: {result}")

if __name__=="__main__":
    main()
