#!/usr/bin/env python3
import argparse, json, os, subprocess, time
from pathlib import Path
import requests
from gradio_client import Client

SPACE=os.getenv("HF_LTX_SPACE","RioShiina/LTX-2.5")

def media_ok(path):
    if not path.exists() or path.stat().st_size < 10000:
        return False
    p=subprocess.run(
        ["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=codec_name","-of","csv=p=0",str(path)],
        capture_output=True,text=True
    )
    return p.returncode==0 and bool(p.stdout.strip())

def download_video(url,out):
    last=None
    for attempt in range(1,5):
        try:
            with requests.get(url,stream=True,timeout=180,headers={"User-Agent":"Mozilla/5.0"}) as r:
                r.raise_for_status()
                ctype=r.headers.get("content-type","")
                with out.open("wb") as fh:
                    for chunk in r.iter_content(1024*1024):
                        if chunk: fh.write(chunk)
                print(f"download attempt={attempt} type={ctype} bytes={out.stat().st_size}")
            if media_ok(out):
                return
            last=RuntimeError("downloaded object is not a valid video")
        except Exception as e:
            last=e
        try: out.unlink()
        except FileNotFoundError: pass
        time.sleep(3*attempt)
    raise RuntimeError(f"video download failed after retries: {last}")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prompt",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--duration",type=float,default=5.0)
    ap.add_argument("--seed",type=int,default=-1)
    ap.add_argument("--resolution",default="768p")
    ap.add_argument("--aspect",default="9:16 (Portrait)")
    a=ap.parse_args()

    params={
      "task_type":"t2v",
      "prompt":a.prompt,
      "negative_prompt":"cartoon, anime, game, distorted hands, deformed faces, warped anatomy, text, watermark, logo",
      "resolution":a.resolution,
      "aspect_ratio":a.aspect,
      "duration":a.duration,
      "fps":"24fps",
      "seed":a.seed,
      "use_spatial_upscaler":False,
      "use_temporal_upscaler":False,
      "zero_gpu_duration":60
    }
    if a.aspect.startswith("9:16"):
        params.update(width=768,height=1344)
    elif a.aspect.startswith("16:9"):
        params.update(width=1344,height=768)

    c=Client(SPACE,verbose=False)
    result=c.predict(json.dumps(params),api_name="/run")
    print("task_id=",result.get("task_id"),"status=",result.get("status"))
    if result.get("status")!="completed":
        raise RuntimeError(json.dumps(result))
    urls=(result.get("result") or {}).get("videos") or []
    if not urls:
        raise RuntimeError("LTX returned no video URL")
    print("video_url=",urls[0])
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    download_video(urls[0],out)
    print(out)

if __name__=="__main__":
    main()
