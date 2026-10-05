#!/usr/bin/env python3
import argparse, json, time, urllib.parse
from pathlib import Path
import requests
from PIL import Image

BASE="https://image.pollinations.ai/prompt"

def valid_image(path):
    try:
        with Image.open(path) as im:
            im.verify()
        return path.stat().st_size > 5000
    except Exception:
        return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--plan",required=True)
    ap.add_argument("--out-dir",required=True)
    ap.add_argument("--count",type=int,default=12)
    ap.add_argument("--delay",type=float,default=0.8)
    a=ap.parse_args()
    plan=json.loads(Path(a.plan).read_text())
    prompts=list(plan.get("scene_prompts") or [])
    while len(prompts)<a.count:
        prompts.extend(plan.get("scene_prompts") or [plan.get("topic","technology")])
    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    ok=0
    manifest=[]
    for i,prompt in enumerate(prompts[:a.count],1):
        dest=out/f"scene_{i:02d}.jpg"
        if valid_image(dest):
            ok+=1
            manifest.append({"index":i,"status":"cached","local":str(dest)})
            continue
        q=(prompt+", cinematic photorealism, natural anatomy, premium documentary photography, vertical 9:16, no readable text, no logo, no watermark")
        url=BASE+"/"+urllib.parse.quote(q)+"?width=768&height=1344&nologo=true&nofeed=true&safe=true&seed="+str(8000+i)
        try:
            r=requests.get(url,timeout=180,headers={"User-Agent":"Mozilla/5.0"})
            r.raise_for_status()
            ctype=r.headers.get("content-type","")
            if "image" not in ctype:
                raise RuntimeError("non-image response "+ctype)
            dest.write_bytes(r.content)
            if not valid_image(dest):
                raise RuntimeError("invalid generated image")
            ok+=1
            manifest.append({"index":i,"status":"ok","local":str(dest),"bytes":dest.stat().st_size,"url":url})
            print("IMAGE_OK",i,dest.stat().st_size)
        except Exception as e:
            dest.unlink(missing_ok=True)
            manifest.append({"index":i,"status":"failed","error":str(e)})
            print("IMAGE_FAIL",i,e)
        time.sleep(a.delay)
    (out/"ai_image_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print("AI_IMAGES_OK",ok,"OF",a.count)
    if ok==0:
        raise SystemExit("No keyless AI images generated")

if __name__=="__main__":
    main()
