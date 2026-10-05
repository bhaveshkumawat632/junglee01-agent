#!/usr/bin/env python3
import argparse, json, os, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent

def clean_title(x):
    return " ".join(str(x).split())[:100]

def clean_desc(x,tags):
    hashes=" ".join("#"+str(t).replace(" ","") for t in tags if t)
    body=(str(x).strip()+"\n\n"+hashes).strip()
    return body[:4900]

def upload(file,title,desc,tags,lang,privacy):
    cmd=[
      sys.executable,HERE/"youtube_upload.py",
      "--file",file,
      "--title",clean_title(title),
      "--description",clean_desc(desc,tags),
      "--tags",",".join(map(str,tags))[:450],
      "--privacy",privacy,
      "--language",lang,
      "--category","27",
    ]
    subprocess.run([str(x) for x in cmd],check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--result",required=True)
    ap.add_argument("--privacy",default="public",choices=["public","unlisted","private"])
    a=ap.parse_args()
    d=json.loads(Path(a.result).read_text())
    if d.get("status")!="READY_FOR_UPLOAD":
        raise SystemExit("Pipeline result is not upload-ready")
    upload(d["final_en"],d["title_en"],d["description_en"],d.get("tags_en",[]),"en",a.privacy)
    upload(d["final_hi"],d["title_hi"],d["description_hi"],d.get("tags_hi",[]),"hi",a.privacy)

if __name__=="__main__":
    main()
