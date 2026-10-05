#!/usr/bin/env python3
"""Cross-check the final English/Hindi pair before upload."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

def audio_hash(path):
    p=subprocess.run([
        "ffmpeg","-nostdin","-v","error","-i",str(path),
        "-map","0:a:0","-ac","1","-ar","16000","-f","s16le","-"
    ],capture_output=True,check=True)
    return hashlib.sha256(p.stdout).hexdigest()

def subtitle_stats(path):
    text=Path(path).read_text(encoding="utf-8").strip()
    cues=len(re.findall(r"(?m)^\d+\s*$",text))
    return {"bytes":len(text.encode("utf-8")),"cues":cues,"text":text}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--en-video",required=True)
    ap.add_argument("--hi-video",required=True)
    ap.add_argument("--en-subtitles",required=True)
    ap.add_argument("--hi-subtitles",required=True)
    ap.add_argument("--min-cues",type=int,default=1)
    a=ap.parse_args()

    en_hash=audio_hash(a.en_video)
    hi_hash=audio_hash(a.hi_video)
    if en_hash==hi_hash:
        raise SystemExit("PAIR QC FAIL: English and Hindi audio are identical")

    en=subtitle_stats(a.en_subtitles)
    hi=subtitle_stats(a.hi_subtitles)
    if en["cues"]<a.min_cues or hi["cues"]<a.min_cues:
        raise SystemExit(
            f"PAIR QC FAIL: insufficient subtitle cues en={en['cues']} "
            f"hi={hi['cues']} required={a.min_cues}"
        )
    if not re.search(r"[\u0900-\u097F]",hi["text"]):
        raise SystemExit("PAIR QC FAIL: Hindi subtitles contain no Devanagari text")

    print(json.dumps({
        "status":"PASS",
        "english_audio_sha256":en_hash,
        "hindi_audio_sha256":hi_hash,
        "audio_streams_differ":True,
        "english_subtitle_cues":en["cues"],
        "hindi_subtitle_cues":hi["cues"],
        "minimum_subtitle_cues_required":a.min_cues,
        "hindi_devanagari_present":True,
    },indent=2))

if __name__=="__main__":
    main()
