#!/usr/bin/env python3
import argparse, json, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageFilter, ImageOps, ImageDraw

def compose(src,dst):
    im=Image.open(src).convert("RGB")
    bg=ImageOps.fit(im,(1080,1920),method=Image.Resampling.LANCZOS)
    bg=bg.filter(ImageFilter.GaussianBlur(28))
    fg=im.copy()
    fg.thumbnail((980,1760),Image.Resampling.LANCZOS)
    canvas=bg
    x=(1080-fg.width)//2; y=(1920-fg.height)//2
    canvas.paste(fg,(x,y))
    canvas.save(dst,quality=92)

def fallback_card(dst,idx):
    im=Image.new("RGB",(1080,1920),(20,20,24))
    d=ImageDraw.Draw(im)
    for y in range(0,1920,120):
        shade=20+int(25*y/1920)
        d.rectangle((0,y,1080,y+120),fill=(shade,shade,shade+6))
    d.ellipse((300,650,780,1130),outline=(210,210,220),width=8)
    d.line((360,960,720,960),fill=(210,210,220),width=8)
    d.line((540,780,540,1140),fill=(210,210,220),width=8)
    im.save(dst,quality=90)

def make_clip(image,out,duration,idx):
    with tempfile.NamedTemporaryFile(suffix=".jpg",delete=False) as t:
        frame=Path(t.name)
    try:
        compose(image,frame)
    except Exception:
        fallback_card(frame,idx)
    zoom="min(zoom+0.00045,1.06)" if idx%2 else "if(lte(zoom,1.0),1.06,max(1.0,zoom-0.00045))"
    x="iw/2-(iw/zoom/2)+8*sin(on/24)"
    y="ih/2-(ih/zoom/2)+6*cos(on/31)"
    subprocess.run([
      "ffmpeg","-nostdin","-y","-loop","1","-framerate","30","-i",str(frame),
      "-vf",f"zoompan=z='{zoom}':x='{x}':y='{y}':d={int(duration*30)}:s=1080x1920:fps=30,format=yuv420p",
      "-t",str(duration),"-an","-c:v","libx264","-preset","veryfast","-crf","21",
      "-movflags","+faststart",str(out)
    ],check=True)
    frame.unlink(missing_ok=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--assets",required=True)
    ap.add_argument("--out-dir",required=True)
    ap.add_argument("--duration",type=float,default=5.0)
    ap.add_argument("--count",type=int,default=12)
    a=ap.parse_args()
    assets=Path(a.assets)
    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    rec=[]
    attr=assets/"attribution.json"
    if attr.exists():
        rec=json.loads(attr.read_text())
    byidx={int(x["index"]):x for x in rec if x.get("status")=="ok" and x.get("local")}
    existing=sorted([p for p in assets.iterdir() if p.suffix.lower() in (".jpg",".jpeg",".png",".webp")])
    for i in range(1,a.count+1):
        src=None
        item=byidx.get(i)
        if item:
            p=Path(item["local"])
            if p.exists(): src=p
        if src is None and existing:
            src=existing[(i-1)%len(existing)]
        dest=out/f"scene_{i:02d}.mp4"
        if src is None:
            tmp=assets/f"fallback_{i:02d}.jpg"
            fallback_card(tmp,i); src=tmp
        make_clip(src,dest,a.duration,i)
        print(dest)

if __name__=="__main__":
    main()
