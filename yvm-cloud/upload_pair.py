#!/usr/bin/env python3
import argparse, json, subprocess, sys
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
    p=subprocess.run([str(x) for x in cmd],check=True,text=True,capture_output=True)
    if p.stderr:
        print(p.stderr,file=sys.stderr,end="")
    print(p.stdout,end="")
    start=p.stdout.rfind("{")
    if start < 0:
        raise RuntimeError(f"YouTube uploader returned no JSON result for {lang}")
    result=json.loads(p.stdout[start:])
    if result.get("status")!="UPLOAD_PASS" or not result.get("video_id"):
        raise RuntimeError(f"YouTube upload did not return a verified video id for {lang}")
    if result.get("privacy")!=privacy:
        raise RuntimeError(f"YouTube upload privacy mismatch for {lang}")
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--result",required=True)
    ap.add_argument("--privacy",default="public",choices=["public","unlisted","private"])
    ap.add_argument("--proof",default="out/daily/youtube_upload_result.json")
    a=ap.parse_args()
    proof_path=Path(a.proof)
    if proof_path.exists():
        try:
            existing_proof = json.loads(proof_path.read_text())
            if existing_proof.get("status") == "PAIR_UPLOAD_PASS":
                print(json.dumps(existing_proof,ensure_ascii=False,indent=2))
                return
        except Exception:
            pass

    d=json.loads(Path(a.result).read_text())
    if d.get("status")!="READY_FOR_UPLOAD":
        raise SystemExit("Pipeline result is not upload-ready")

    en=upload(d["final_en"],d["title_en"],d["description_en"],d.get("tags_en",[]),"en",a.privacy)
    hi=upload(d["final_hi"],d["title_hi"],d["description_hi"],d.get("tags_hi",[]),"hi",a.privacy)
    if en["video_id"] == hi["video_id"]:
        raise RuntimeError("English and Hindi uploads returned the same YouTube video id")

    proof={
        "status":"PAIR_UPLOAD_PASS",
        "privacy":a.privacy,
        "english":en,
        "hindi":hi,
    }
    proof_path=Path(a.proof)
    proof_path.parent.mkdir(parents=True,exist_ok=True)
    proof_path.write_text(json.dumps(proof,ensure_ascii=False,indent=2))
    print(json.dumps(proof,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
