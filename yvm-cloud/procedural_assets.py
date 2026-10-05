#!/usr/bin/env python3
import argparse, json, math, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

W,H=768,1344

def existing(out,i):
    for ext in (".jpg",".jpeg",".png",".webp"):
        p=out/f"scene_{i:02d}{ext}"
        if p.exists() and p.stat().st_size>10000:
            return p
    return None

def bg(seed):
    rng=random.Random(seed)
    top=(12+rng.randrange(10),18+rng.randrange(10),28+rng.randrange(14))
    bot=(30+rng.randrange(28),32+rng.randrange(22),38+rng.randrange(20))
    im=Image.new("RGB",(W,H))
    d=ImageDraw.Draw(im)
    for y in range(H):
        t=y/(H-1)
        c=tuple(int(top[k]*(1-t)+bot[k]*t) for k in range(3))
        d.line((0,y,W,y),fill=c)
    return im,rng

def screen(d,box,rng):
    x1,y1,x2,y2=box
    d.rounded_rectangle(box,radius=18,fill=(28,42,52),outline=(105,125,138),width=3)
    for x in range(x1+25,x2-10,50):
        d.line((x,y1+18,x,y2-20),fill=(43,62,72),width=1)
    for y in range(y1+35,y2-15,45):
        d.line((x1+15,y,x2-15,y),fill=(43,62,72),width=1)
    pts=[]
    for k in range(7):
        x=x1+22+int((x2-x1-44)*k/6)
        y=y2-40-rng.randrange(max(30,y2-y1-90))
        pts.append((x,y))
    d.line(pts,fill=(190,210,218),width=5)

def people_floor(d,rng):
    for row in range(3):
        y=410+row*235
        for col in range(4):
            x=95+col*165+(row%2)*25
            head=(x-18,y-95,x+18,y-59)
            d.ellipse(head,fill=(132+rng.randrange(35),105+rng.randrange(30),82+rng.randrange(20)))
            d.polygon([(x-45,y-55),(x+45,y-55),(x+60,y+70),(x-60,y+70)],fill=(45+rng.randrange(25),48+rng.randrange(25),55+rng.randrange(28)))
            d.rectangle((x-72,y+78,x+72,y+102),fill=(60,52,46))
            screen(d,(x-60,y+110,x+60,y+215),rng)

def phone(d):
    d.arc((180,410,590,830),start=205,end=335,fill=(185,190,190),width=38)
    d.rounded_rectangle((190,720,575,865),radius=32,fill=(42,44,48),outline=(120,125,128),width=4)
    d.rounded_rectangle((245,470,520,580),radius=50,fill=(55,57,60),outline=(135,138,140),width=4)
    for r in range(3):
        for c in range(4):
            x=285+c*65; y=755+r*34
            d.ellipse((x-7,y-7,x+7,y+7),fill=(145,145,140))

def papers(d,rng):
    for n in range(5):
        x=120+n*65; y=330+n*105
        d.rounded_rectangle((x,y,x+420,y+300),radius=8,fill=(220-n*8,216-n*8,202-n*5),outline=(120,115,108),width=2)
        pts=[]
        for k in range(7):
            px=x+35+k*52
            py=y+220-rng.randrange(140)
            pts.append((px,py))
        d.line(pts,fill=(65,75,84),width=4)
        for yy in range(y+45,y+150,28):
            d.line((x+35,yy,x+270,yy),fill=(160,158,150),width=2)

def building(d):
    d.rectangle((100,350,668,1110),fill=(72,74,78),outline=(160,160,155),width=4)
    d.polygon([(75,350),(384,180),(693,350)],fill=(105,103,98),outline=(180,178,170))
    for x in range(150,650,95):
        d.rectangle((x,420,x+48,1040),fill=(125,124,118),outline=(175,174,166),width=3)
    d.rectangle((85,1040,683,1115),fill=(95,94,90))

def workstation(d,rng):
    screen(d,(80,270,365,600),rng)
    screen(d,(405,235,690,565),rng)
    d.rectangle((70,670,700,740),fill=(72,60,50))
    d.ellipse((300,780,470,950),fill=(64,60,58))
    d.polygon([(270,930),(500,930),(580,1250),(190,1250)],fill=(44,46,52))

def generic_dashboard(d,rng):
    screen(d,(80,260,688,680),rng)
    for i in range(8):
        x=95+i*75
        h=90+rng.randrange(300)
        d.rounded_rectangle((x,1120-h,x+42,1120),radius=8,fill=(90+rng.randrange(45),120+rng.randrange(45),135+rng.randrange(40)))
    d.line([(90,1020),(210,870),(330,940),(470,740),(650,820)],fill=(220,215,190),width=8)

def render(prompt,idx,path):
    im,rng=bg(9000+idx)
    d=ImageDraw.Draw(im)
    p=prompt.lower()
    if any(k in p for k in ("phone","telephone","receiver")):
        phone(d)
        screen(d,(85,210,300,410),rng)
    elif any(k in p for k in ("paper","notepad","newspaper","printout","calculator")):
        papers(d,rng)
    elif any(k in p for k in ("exterior","building","wall street","stock exchange")) and "floor" not in p:
        building(d)
    elif any(k in p for k in ("trading floor","traders","crowd","group")):
        people_floor(d,rng)
    elif any(k in p for k in ("computer","monitor","terminal","screen","workstation")):
        workstation(d,rng)
    else:
        generic_dashboard(d,rng)
    # Practical lights and mild photographic softness.
    for _ in range(12):
        x=rng.randrange(W); y=rng.randrange(150,H-100); r=rng.randrange(5,18)
        d.ellipse((x-r,y-r,x+r,y+r),fill=(180+rng.randrange(50),135+rng.randrange(55),70+rng.randrange(45)))
    im=im.filter(ImageFilter.GaussianBlur(0.6))
    im.save(path,quality=92)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--plan",required=True)
    ap.add_argument("--out-dir",required=True)
    ap.add_argument("--count",type=int,default=12)
    a=ap.parse_args()
    plan=json.loads(Path(a.plan).read_text())
    prompts=list(plan.get("scene_prompts") or [])
    topic=plan.get("topic") or "technology finance"
    while len(prompts)<a.count:
        prompts.append(topic)
    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    made=[]
    for i,prompt in enumerate(prompts[:a.count],1):
        if existing(out,i):
            continue
        dest=out/f"scene_{i:02d}.jpg"
        render(prompt,i,dest)
        made.append({"index":i,"prompt":prompt,"local":str(dest),"bytes":dest.stat().st_size})
        print("PROCEDURAL_ASSET",i,dest)
    (out/"procedural_manifest.json").write_text(json.dumps(made,ensure_ascii=False,indent=2))
    print("PROCEDURAL_FILLED",len(made))

if __name__=="__main__":
    main()
