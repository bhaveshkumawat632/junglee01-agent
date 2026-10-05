#!/usr/bin/env python3
import argparse, os, time
from pathlib import Path
import requests

BASE="https://apihub.agnes-ai.com/v1"
POLL="https://apihub.agnes-ai.com/agnesapi"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--duration", type=int, default=5)
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=1152)
    ap.add_argument("--reference-url")
    args=ap.parse_args()

    key=os.environ.get("AGNES_API_KEY")
    if not key:
        raise SystemExit("AGNES_API_KEY is not configured")

    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}
    frames=min(args.duration*24+1,409)
    payload={
        "model":"agnes-video-v2.0",
        "prompt":args.prompt,
        "width":args.width,
        "height":args.height,
        "num_frames":frames,
        "frame_rate":24,
    }
    if args.reference_url:
        payload["image"]=args.reference_url
        payload["mode"]="ti2vid"

    r=requests.post(f"{BASE}/videos",headers=headers,json=payload,timeout=(15,90))
    r.raise_for_status()
    data=r.json()
    video_id=data.get("video_id") or data.get("task_id") or data.get("id")
    if not video_id:
        raise RuntimeError(f"No video id returned: {data}")

    deadline=time.time()+1800
    final=None
    while time.time()<deadline:
        p=requests.get(POLL,params={"video_id":video_id},headers=headers,timeout=30)
        p.raise_for_status()
        final=p.json()
        status=str(final.get("status","")).lower()
        print("status=",status,"progress=",final.get("progress"))
        if status=="completed":
            break
        if status=="failed":
            raise RuntimeError(final.get("error") or "Agnes generation failed")
        time.sleep(45)
    else:
        raise TimeoutError("Agnes video generation timed out")

    url=final.get("video_url") or final.get("url") or final.get("remixed_from_video_id")
    if not url and isinstance(final.get("data"),dict):
        url=final["data"].get("video_url") or final["data"].get("url")
    if not url:
        raise RuntimeError(f"No completed video URL: {final}")

    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    with requests.get(url,stream=True,timeout=180) as d:
        d.raise_for_status()
        with out.open("wb") as f:
            for chunk in d.iter_content(1024*1024):
                if chunk: f.write(chunk)
    print(out)
if __name__=="__main__":
    main()
