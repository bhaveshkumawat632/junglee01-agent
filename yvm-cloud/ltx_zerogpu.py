#!/usr/bin/env python3
import argparse, json, requests
from pathlib import Path
from gradio_client import Client

SPACE="RioShiina/LTX-2.5"

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
    if result.get("status")!="completed":
        raise RuntimeError(json.dumps(result))
    urls=(result.get("result") or {}).get("videos") or []
    if not urls:
        raise RuntimeError("LTX returned no video URL")
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    with requests.get(urls[0],stream=True,timeout=180) as r:
        r.raise_for_status()
        with out.open("wb") as f:
            for chunk in r.iter_content(1024*1024):
                if chunk: f.write(chunk)
    print(out)
if __name__=="__main__":
    main()
