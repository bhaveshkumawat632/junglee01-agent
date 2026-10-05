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
    # Deterministic text-free documentary/data visual used only when every
    # external visual source is unavailable. It avoids a blank placeholder.
    im=Image.new("RGB",(1080,1920),(14,18,26))
    d=ImageDraw.Draw(im)

    # Vertical cinematic gradient.
    for y in range(1920):
        t=y/1919
        r=int(14+22*t); g=int(18+26*t); b=int(26+34*t)
        d.line((0,y,1080,y),fill=(r,g,b))

    # Soft "monitor" panels.
    panels=[
        (90,260,490,720),(590,210,990,670),
        (120,820,520,1260),(570,790,970,1230)
    ]
    for j,(x1,y1,x2,y2) in enumerate(panels):
        base=38+((idx*11+j*17)%28)
        d.rounded_rectangle((x1,y1,x2,y2),radius=28,
                            fill=(base,base+8,base+14),
                            outline=(100,120,135),width=4)
        # Grid.
        for gx in range(x1+40,x2-20,70):
            d.line((gx,y1+35,gx,y2-35),fill=(55,70,82),width=2)
        for gy in range(y1+55,y2-25,65):
            d.line((x1+25,gy,x2-25,gy),fill=(55,70,82),width=2)

        # Deterministic chart-like line with no readable text.
        pts=[]
        span=max(1,x2-x1-70)
        for k in range(8):
            x=x1+35+int(span*k/7)
            y=y2-70-((idx*53+j*71+k*47+k*k*13)%(y2-y1-150))
            pts.append((x,y))
        d.line(pts,fill=(185,205,218),width=7)
        for x,y in pts:
            d.ellipse((x-8,y-8,x+8,y+8),fill=(220,225,230))

    # Foreground desk and practical-light shapes.
    d.polygon([(0,1510),(1080,1420),(1080,1920),(0,1920)],fill=(24,22,22))
    d.ellipse((760,1320,1020,1580),fill=(95,78,58))
    d.ellipse((790,1350,990,1550),fill=(190,154,92))
    d.rectangle((110,1470,520,1510),fill=(76,68,58))

    # Slight blur for photographic softness.
    im=im.filter(ImageFilter.GaussianBlur(0.7))
    im.save(dst,quality=92)

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
        direct=[]
        for ext in (".jpg",".jpeg",".png",".webp"):
            p=assets/f"scene_{i:02d}{ext}"
            if p.exists():
                direct.append(p)
        if direct:
            src=direct[0]
        item=byidx.get(i)
        if src is None and item:
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
