#!/usr/bin/env python3
import argparse, os, shutil, subprocess
from pathlib import Path
from gradio_client import Client

SPACE=os.getenv("HF_WAN_SPACE","numanajmal0/Wan-Video-API")

def valid_video(path):
    p=Path(path)
    if not p.is_file() or p.stat().st_size < 10000:
        return False
    q=subprocess.run([
        "ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","stream=codec_name,width,height",
        "-show_entries","format=duration","-of","default=noprint_wrappers=1",str(p)
    ],capture_output=True,text=True)
    return q.returncode==0 and "codec_name=" in q.stdout

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prompt",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--seed",type=int,default=42)
    ap.add_argument("--frames",type=int)
    ap.add_argument("--duration",type=float,default=3.0)
    ap.add_argument("--steps",type=int,default=8)
    ap.add_argument("--width",type=int,default=480)
    ap.add_argument("--height",type=int,default=832)
    a=ap.parse_args()

    frames=a.frames
    if frames is None:
        raw=max(21,min(81,round(a.duration*16)))
        frames=max(21,min(81,4*round((raw-1)/4)+1))
    print(f"WAN_CONFIG frames={frames} duration_target={a.duration} steps={a.steps}",flush=True)

    client=Client(SPACE,verbose=False)
    result=client.predict(
        "wan-base",
        a.prompt,
        "cartoon, anime, text, watermark, logo, distorted anatomy, deformed face, extra fingers, blurry",
        a.width,
        a.height,
        frames,
        a.steps,
        5.0,
        a.seed,
        1.0,
        "",
        api_name="/generate",
    )
    print("WAN_RESULT",result,flush=True)
    path=result[0] if isinstance(result,(tuple,list)) else result
    if isinstance(path,dict):
        path=path.get("video") or path.get("path")
    if not path or not os.path.exists(path):
        raise SystemExit("Wan API returned no local video file")
    out=Path(a.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,out)
    if not valid_video(out):
        out.unlink(missing_ok=True)
        raise SystemExit("Wan API output failed video validation")
    print(out)

if __name__=="__main__":
    main()
