#!/usr/bin/env python3
"""Lightweight metadata/script gate for a YVM daily plan."""
import argparse
import json
import re
from pathlib import Path

DEVANAGARI=re.compile(r"[\u0900-\u097F]")
GARBAGE_TITLE=re.compile(
    r"(?i)(?:^|\b)(?:final[_ -]?video|output|render|scene[_ -]?\d+|"
    r"\d{8}[_-]\d{6}|\d{4}[-_]\d{2}[-_]\d{2})(?:\b|$)"
)

def text(d,key):
    return str(d.get(key) or "").strip()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--min-scenes",type=int,default=8)
    a=ap.parse_args()
    d=json.loads(Path(a.plan).read_text(encoding="utf-8"))

    required=["topic","title_en","title_hi","description_en","description_hi","script_en","script_hi"]
    missing=[k for k in required if not text(d,k)]
    if missing:
        raise SystemExit("PLAN QC FAIL: missing "+", ".join(missing))

    en=text(d,"title_en")
    hi=text(d,"title_hi")
    if en==hi:
        raise SystemExit("PLAN QC FAIL: English and Hindi titles are identical")
    if GARBAGE_TITLE.search(en) or GARBAGE_TITLE.search(hi):
        raise SystemExit("PLAN QC FAIL: filename/timestamp-style title detected")
    if len(en)>100 or len(hi)>100:
        raise SystemExit("PLAN QC FAIL: title exceeds 100 characters")
    if not DEVANAGARI.search(hi):
        raise SystemExit("PLAN QC FAIL: Hindi title has no Devanagari text")
    if not DEVANAGARI.search(text(d,"script_hi")):
        raise SystemExit("PLAN QC FAIL: Hindi script has no Devanagari text")
    if text(d,"script_en")==text(d,"script_hi"):
        raise SystemExit("PLAN QC FAIL: English and Hindi scripts are identical")

    scenes=list(d.get("scene_prompts") or [])
    if len(scenes)<a.min_scenes:
        raise SystemExit(
            f"PLAN QC FAIL: only {len(scenes)} scene prompts; need {a.min_scenes}"
        )
    checked=[str(x).strip() for x in scenes[:a.min_scenes]]
    if any(len(x)<180 for x in checked):
        raise SystemExit("PLAN QC FAIL: one or more scene prompts are too short for production-quality visual direction")

    required_visual_terms=("photorealistic","no visible words","no logos","no mannequins","no distorted anatomy","no 3d render")
    for idx,prompt in enumerate(checked,1):
        low=prompt.lower()
        missing_terms=[x for x in required_visual_terms if x not in low]
        if missing_terms:
            raise SystemExit(
                f"PLAN QC FAIL: scene {idx} missing visual safety contract: "+", ".join(missing_terms)
            )

    topic_tokens=[
        x for x in re.findall(r"[A-Za-z]{3,}", text(d,"topic").lower())
        if x not in {"the","and","for","with","from","that","this","global","magazine"}
    ]
    topical=sum(1 for p in checked if any(tok in p.lower() for tok in topic_tokens))
    if topic_tokens and topical < max(4, a.min_scenes//2):
        raise SystemExit(
            f"PLAN QC FAIL: only {topical} scene prompts are explicitly tied to the topic"
        )

    tags_en=list(d.get("tags_en") or [])
    tags_hi=list(d.get("tags_hi") or [])
    if not tags_en or not tags_hi:
        raise SystemExit("PLAN QC FAIL: language-specific tags missing")

    print(json.dumps({
        "status":"PASS",
        "topic":text(d,"topic"),
        "title_en_length":len(en),
        "title_hi_length":len(hi),
        "scene_prompt_count":len(scenes),
        "tags_en_count":len(tags_en),
        "tags_hi_count":len(tags_hi),
        "hindi_devanagari_present":True,
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
