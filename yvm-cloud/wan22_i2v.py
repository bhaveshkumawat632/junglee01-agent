#!/usr/bin/env python3
import argparse, os, shutil, subprocess
from pathlib import Path
from gradio_client import Client, handle_file

SPACE=os.getenv("HF_WAN22_I2V_SPACE","zerogpu-aoti/wan2-2-fp8da-aoti-faster")

def find_video(value):
    found=[]
    def walk(v):
        if isinstance(v,str):
            found.append(v)
        elif isinstance(v,dict):
            for z in v.values(): walk(z)
        elif isinstance(v,(list,tuple)):
            for z in v: walk(z)
    walk(value)
    for p in found:
        if p and os.path.exists(p) and p.lower().endswith((".mp4",".webm",".mov")):
            return p
    return None

def valid_video(path):
    q=subprocess.run([
        "ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","stream=codec_name,width,height",
        "-show_entries","format=duration","-of","default=noprint_wrappers=1",str(path)
    ],capture_output=True,text=True)
    return q.returncode==0 and "codec_name=" in q.stdout

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--image",required=True)
    ap.add_argument("--prompt",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--duration",type=float,default=2.0)
    ap.add_argument("--steps",type=int,default=4)
    ap.add_argument("--seed",type=int,default=42)
    a=ap.parse_args()

    image=Path(a.image)
    if not image.is_file():
        raise SystemExit("Input image missing")

    c=Client(SPACE,verbose=False)
    result=c.predict(
        handle_file(str(image)),
        a.prompt,
        a.steps,
        "static, blurry, distorted anatomy, deformed face, extra fingers, text, watermark, logo",
        a.duration,
        3.5,
        3.5,
        a.seed,
        False,
        api_name="/generate_video",
    )
    print("WAN22_RESULT",result,flush=True)
    src=find_video(result)
    if not src:
        raise SystemExit("Wan2.2 Space returned no local video")
    out=Path(a.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,out)
    if not valid_video(out):
        out.unlink(missing_ok=True)
        raise SystemExit("Wan2.2 output failed video validation")
    print(out)

if __name__=="__main__":
    main()
