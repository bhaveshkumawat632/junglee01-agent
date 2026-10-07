#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

GARBAGE_TITLE = re.compile(
    r"(?:^|\b)(?:final[_\s-]*video|output|render|scene[_\s-]*\d+|\d{8}[_\s-]*\d{6})(?:\b|$)",
    re.I,
)

STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "global", "magazine",
    "what", "how", "why", "when", "where", "which", "into", "over", "about",
    "your", "does", "been", "have", "will", "more", "their", "they", "them",
    "there", "here", "are", "changing", "behind", "matter", "matters", "story",
}


def text(d, key):
    return str(d.get(key) or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--min-scenes", type=int, default=8)
    a = ap.parse_args()

    p = Path(a.plan)
    if not p.exists():
        raise SystemExit(f"PLAN QC FAIL: plan file does not exist: {p}")

    d = json.loads(p.read_text(encoding="utf-8"))

    required = [
        "topic", "title_en", "title_hi", "description_en", "description_hi",
        "script_en", "script_hi",
    ]
    for k in required:
        if not text(d, k):
            raise SystemExit(f"PLAN QC FAIL: missing required field '{k}'")

    if text(d, "title_en") == text(d, "title_hi"):
        raise SystemExit("PLAN QC FAIL: English and Hindi titles are identical")

    for k in ("title_en", "title_hi"):
        if GARBAGE_TITLE.search(text(d, k)):
            raise SystemExit(
                f"PLAN QC FAIL: garbage/placeholder pattern detected in {k}: '{text(d, k)}'"
            )
        if len(text(d, k)) > 100:
            raise SystemExit(
                f"PLAN QC FAIL: {k} exceeds 100 characters ({len(text(d, k))})"
            )

    if not re.search(r"[\u0900-\u097F]", text(d, "title_hi")):
        raise SystemExit("PLAN QC FAIL: Hindi title contains no Devanagari characters")

    if not re.search(r"[\u0900-\u097F]", text(d, "script_hi")):
        raise SystemExit("PLAN QC FAIL: Hindi script contains no Devanagari characters")

    if text(d, "script_en") == text(d, "script_hi"):
        raise SystemExit("PLAN QC FAIL: English and Hindi scripts are identical")

    bad_starters = (
        "hello", "today we", "in this video", "here is the story",
        "here is what", "hey guys",
    )
    en_low = text(d, "script_en").lower()
    if any(en_low.startswith(s) for s in bad_starters):
        raise SystemExit(
            "PLAN QC FAIL: English script starts with a generic opening instead of a high-retention hook"
        )

    prompts = d.get("scene_prompts")
    if not isinstance(prompts, list):
        raise SystemExit("PLAN QC FAIL: scene_prompts must be a list")
    if len(prompts) < a.min_scenes:
        raise SystemExit(
            f"PLAN QC FAIL: insufficient scene prompts ({len(prompts)} < {a.min_scenes})"
        )

    checked = [str(x or "").strip() for x in prompts[:a.min_scenes]]

    required_safety_terms = [
        "photorealistic",
        "no visible words",
        "no logos",
        "no mannequins",
        "no distorted anatomy",
        "no 3d render",
    ]
    for idx, prompt_str in enumerate(checked, 1):
        if len(prompt_str) < 180:
            raise SystemExit(
                f"PLAN QC FAIL: scene {idx} prompt is too short ({len(prompt_str)} < 180 chars)"
            )
        low = prompt_str.lower()
        for term in required_safety_terms:
            if term not in low:
                raise SystemExit(
                    f"PLAN QC FAIL: scene {idx} missing required safety term '{term}'"
                )

    topic_tokens = [
        x
        for x in re.findall(r"[A-Za-z]{3,}", text(d, "topic").lower())
        if x not in STOP_WORDS
    ]
    topical = sum(
        1 for prompt in checked if any(tok in prompt.lower() for tok in topic_tokens)
    )
    required_topical = a.min_scenes

    if topic_tokens and topical < required_topical:
        raise SystemExit(
            f"PLAN QC FAIL: only {topical} scene prompts are explicitly tied to the topic "
            f"(required: {required_topical})"
        )

    for k in ("tags_en", "tags_hi"):
        tags = d.get(k)
        if not isinstance(tags, list) or not tags:
            raise SystemExit(f"PLAN QC FAIL: {k} must be a non-empty list of tags")

    result = {
        "status": "PLAN_QC_PASS",
        "topic": text(d, "topic"),
        "topical_scene_count": topical,
        "checked_scenes": len(checked),
        "topic_tokens": topic_tokens,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
