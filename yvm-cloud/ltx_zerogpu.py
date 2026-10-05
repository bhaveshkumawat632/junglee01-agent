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
        ["ffprobe","-v","error","-select_streams","v:0",
         "-show_entries","stream=codec_name,width,height",
         "-show_entries","format=duration",
         "-of","json",str(path)],
        capture_output=True,text=True
    )
    if p.returncode != 0:
        return False
    try:
        d=json.loads(p.stdout)
        s=(d.get("streams") or [{}])[0]
        dur=float((d.get("format") or {}).get("duration") or 0)
        return bool(s.get("codec_name")) and int(s.get("width") or 0)>0 and int(s.get("height") or 0)>0 and dur>1
    except Exception:
        return False

def download_video(url,out):
    last=None
    for attempt in range(1,5):
        try:
            with requests.get(url,stream=True,timeout=180,headers={"User-Agent":"Mozilla/5.0"}) as r:
                r.raise_for_status()
                ctype=r.headers.get("content-type","")
                with out.open("wb") as fh:
                    for chunk in r.iter_content(1024*1024):
                        if chunk:
                            fh.write(chunk)
                print(f"download attempt={attempt} type={ctype} bytes={out.stat().st_size}",flush=True)
            if media_ok(out):
                return
            last=RuntimeError("downloaded object is not a valid playable video")
        except Exception as e:
            last=e
        out.unlink(missing_ok=True)
        time.sleep(min(15,3*attempt))
    raise RuntimeError(f"video download failed after retries: {last}")

def generate_once(params,out):
    c=Client(SPACE,verbose=False)
    result=c.predict(json.dumps(params),api_name="/run")
    print("task_id=",result.get("task_id"),"status=",result.get("status"),flush=True)
    if result.get("status")!="completed":
        raise RuntimeError(json.dumps(result))
    urls=(result.get("result") or {}).get("videos") or []
    if not urls:
        raise RuntimeError("LTX returned no video URL")
    print("video_url=",urls[0],flush=True)
    download_video(urls[0],out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prompt",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--duration",type=float,default=5.0)
    ap.add_argument("--seed",type=int,default=-1)
    ap.add_argument("--resolution",default="768p")
    ap.add_argument("--aspect",default="9:16 (Portrait)")
    ap.add_argument("--attempts",type=int,default=2)
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

    out=Path(a.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    last=None
    for attempt in range(1,max(1,a.attempts)+1):
        out.unlink(missing_ok=True)
        try:
            print(f"generation attempt={attempt}/{a.attempts} space={SPACE}",flush=True)
            generate_once(params,out)
            if not media_ok(out):
                raise RuntimeError("generated output failed local media validation")
            print(out)
            return
        except Exception as e:
            last=e
            print(f"generation attempt {attempt} failed: {type(e).__name__}: {e}",flush=True)
            if attempt < a.attempts:
                time.sleep(min(30,8*attempt))
    raise SystemExit(f"LTX generation failed after {a.attempts} attempts: {last}")

if __name__=="__main__":
    main()
