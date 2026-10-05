#!/usr/bin/env python3
import argparse, html, json, re, time
from pathlib import Path
import requests

API="https://commons.wikimedia.org/w/api.php"
UA="YVM-Cloud/2.0 (https://github.com/bhaveshkumawat632/junglee01-agent)"
STOP=set("""cinematic realistic vertical documentary photo photography shot scene camera lighting natural people person close macro wide dramatic premium modern no text logo logos readable abstract motion composition with and the of in on at from to a an for""".split())

def clean_query(text):
    words=re.findall(r"[A-Za-z0-9][A-Za-z0-9.+-]*",text)
    words=[w for w in words if w.lower() not in STOP and len(w)>2]
    return " ".join(words[:7]) or "technology business"

def get_json(params, attempts=5):
    last=None
    for attempt in range(1,attempts+1):
        try:
            r=requests.get(API,params=params,headers={"User-Agent":UA},timeout=30)
            if r.status_code in (429,500,502,503,504):
                retry=r.headers.get("Retry-After")
                delay=float(retry) if retry and retry.isdigit() else min(12,1.5*(2**(attempt-1)))
                print(f"commons retry status={r.status_code} attempt={attempt} sleep={delay}")
                time.sleep(delay)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last=e
            if attempt<attempts:
                time.sleep(min(12,1.5*(2**(attempt-1))))
    raise RuntimeError(f"Commons API failed after retries: {last}")

def search(query,limit=12):
    params={
      "action":"query","format":"json","formatversion":2,
      "generator":"search","gsrsearch":f"{query} filetype:bitmap","gsrnamespace":6,"gsrlimit":limit,
      "prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":1400,
      "maxlag":5
    }
    data=get_json(params)
    pages=(data.get("query") or {}).get("pages") or []
    out=[]
    for p in pages:
        ii=(p.get("imageinfo") or [{}])[0]
        url=ii.get("thumburl") or ii.get("url")
        if not url:
            continue
        low=url.lower().split("?")[0]
        if not low.endswith((".jpg",".jpeg",".png",".webp")):
            continue
        title=p.get("title","")
        title_low=title.lower()
        if title_low.endswith((".pdf",".djvu",".tif",".tiff",".xcf",".psd")):
            continue
        width=ii.get("thumbwidth") or ii.get("width") or 0
        height=ii.get("thumbheight") or ii.get("height") or 0
        if int(width or 0) < 300 or int(height or 0) < 300:
            continue
        meta=ii.get("extmetadata") or {}
        def m(k):
            return html.unescape(re.sub("<[^>]+>","",str((meta.get(k) or {}).get("value","")))).strip()
        out.append({
          "title":title,
          "url":url,
          "page_url":"https://commons.wikimedia.org/wiki/"+title.replace(" ","_"),
          "artist":m("Artist"),
          "license":m("LicenseShortName") or m("UsageTerms"),
          "credit":m("Credit"),
          "width":width,
          "height":height,
        })
    return out

def download(url,path,attempts=4):
    last=None
    for attempt in range(1,attempts+1):
        try:
            r=requests.get(url,headers={"User-Agent":UA},timeout=60)
            if r.status_code in (429,500,502,503,504):
                time.sleep(min(10,2*attempt))
                continue
            r.raise_for_status()
            if "image" not in r.headers.get("content-type",""):
                raise RuntimeError("not an image")
            path.write_bytes(r.content)
            return len(r.content)
        except Exception as e:
            last=e
            if attempt<attempts:
                time.sleep(min(10,2*attempt))
    raise RuntimeError(f"image download failed: {last}")

def existing_scene(out,index):
    for ext in (".jpg",".jpeg",".png",".webp"):
        p=out/f"scene_{index:02d}{ext}"
        if p.exists() and p.stat().st_size>10000:
            return p
    return None

def next_unused(candidates,used):
    for c in candidates:
        if c["url"] not in used:
            return c
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--plan",required=True)
    ap.add_argument("--out-dir",default="out/assets")
    ap.add_argument("--count",type=int,default=12)
    ap.add_argument("--unique-searches",type=int,default=6)
    a=ap.parse_args()
    plan=json.loads(Path(a.plan).read_text())
    prompts=list(plan.get("scene_prompts") or [])
    topic=plan.get("topic") or "technology business"
    while len(prompts)<a.count:
        prompts.append(topic)

    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    records=[]; used=set(); cache={}

    def cached(q):
        if q not in cache:
            cache[q]=search(q)
            time.sleep(0.8)
        return cache[q]

    # Search broad reusable pools once. This prevents repeated generic API calls.
    fallback=[]
    for q in (clean_query(topic),f"{clean_query(topic)} historical", "stock exchange trading floor finance computer"):
        try:
            fallback.extend(cached(q))
        except Exception as e:
            print("fallback search warning",q,e)

    for i,prompt in enumerate(prompts[:a.count],1):
        present=existing_scene(out,i)
        if present:
            records.append({
                "index":i,"status":"existing_non_commons","prompt":prompt,
                "local":str(present),"bytes":present.stat().st_size
            })
            continue

        chosen=None
        if i <= max(0,a.unique_searches):
            q=clean_query(prompt)
            try:
                chosen=next_unused(cached(q),used)
            except Exception as e:
                print("search warning",q,e)
        if not chosen:
            chosen=next_unused(fallback,used)
        if not chosen:
            records.append({"index":i,"status":"missing","prompt":prompt})
            continue

        ext=".png" if ".png" in chosen["url"].lower().split("?")[0] else ".jpg"
        dest=out/f"scene_{i:02d}{ext}"
        try:
            size=download(chosen["url"],dest)
            used.add(chosen["url"])
            chosen.update({"index":i,"status":"ok","prompt":prompt,"local":str(dest),"bytes":size})
            records.append(chosen)
            print(i,chosen["title"],size)
        except Exception as e:
            records.append({"index":i,"status":"missing","prompt":prompt,"error":str(e)})
        time.sleep(0.35)

    (out/"attribution.json").write_text(json.dumps(records,ensure_ascii=False,indent=2))
    good=sum(x.get("status") in ("ok","existing_non_commons") for x in records)
    print("ASSETS_OK",good,"OF",a.count)
    if good < a.count:
        print("COMMONS_DEGRADED: procedural CPU fallback will fill missing scenes")

if __name__=="__main__":
    main()
