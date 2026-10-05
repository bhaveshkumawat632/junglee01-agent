#!/usr/bin/env python3
import argparse, html, json, re, time
from pathlib import Path
from urllib.parse import urlparse
import requests

API="https://commons.wikimedia.org/w/api.php"
UA="YVM-Cloud/1.0 (educational YouTube automation)"

STOP=set("""cinematic realistic vertical documentary photo photography shot scene camera lighting natural people person close macro wide dramatic premium modern no text logo logos readable abstract motion composition with and the of in on at from to a an for""".split())

def clean_query(text):
    words=re.findall(r"[A-Za-z0-9][A-Za-z0-9.+-]*",text)
    words=[w for w in words if w.lower() not in STOP and len(w)>2]
    return " ".join(words[:7]) or "technology business"

def search(query,limit=8):
    params={
      "action":"query","format":"json","generator":"search",
      "gsrsearch":query,"gsrnamespace":6,"gsrlimit":limit,
      "prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":1400
    }
    r=requests.get(API,params=params,headers={"User-Agent":UA},timeout=30)
    r.raise_for_status()
    pages=(r.json().get("query") or {}).get("pages") or {}
    out=[]
    for p in pages.values():
        ii=(p.get("imageinfo") or [{}])[0]
        url=ii.get("thumburl") or ii.get("url")
        if not url:
            continue
        low=url.lower().split("?")[0]
        if not low.endswith((".jpg",".jpeg",".png",".webp")):
            continue
        meta=ii.get("extmetadata") or {}
        def m(k):
            return html.unescape(re.sub("<[^>]+>","",str((meta.get(k) or {}).get("value","")))).strip()
        out.append({
          "title":p.get("title",""),
          "url":url,
          "page_url":"https://commons.wikimedia.org/wiki/"+p.get("title","").replace(" ","_"),
          "artist":m("Artist"),
          "license":m("LicenseShortName") or m("UsageTerms"),
          "credit":m("Credit"),
          "width":ii.get("thumbwidth") or ii.get("width"),
          "height":ii.get("thumbheight") or ii.get("height"),
        })
    return out

def download(url,path):
    r=requests.get(url,headers={"User-Agent":UA},timeout=60)
    r.raise_for_status()
    if "image" not in r.headers.get("content-type",""):
        raise RuntimeError("not an image")
    path.write_bytes(r.content)
    return len(r.content)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--plan",required=True)
    ap.add_argument("--out-dir",default="out/assets")
    ap.add_argument("--count",type=int,default=12)
    a=ap.parse_args()
    plan=json.loads(Path(a.plan).read_text())
    prompts=list(plan.get("scene_prompts") or [])
    topic=plan.get("topic") or "technology business"
    while len(prompts)<a.count:
        prompts.append(topic)

    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    records=[]
    used=set()
    for i,prompt in enumerate(prompts[:a.count],1):
        queries=[clean_query(prompt),clean_query(topic),"technology business finance"]
        chosen=None
        for q in queries:
            try:
                for c in search(q):
                    if c["url"] not in used:
                        chosen=c; break
                if chosen: break
            except Exception as e:
                print("search warning",q,e)
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
        time.sleep(0.15)

    (out/"attribution.json").write_text(json.dumps(records,ensure_ascii=False,indent=2))
    good=sum(x.get("status") in ("ok","existing_non_commons") for x in records)
    print("ASSETS_OK",good,"OF",a.count)
    if good < max(4,a.count//2):
        raise SystemExit("Too few Commons assets")

if __name__=="__main__":
    main()
