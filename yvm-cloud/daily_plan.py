#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

LLM7_BASE = "https://api.llm7.io/v1"
POLLINATIONS_URL = "https://text.pollinations.ai/openai"
LLMFAUCET_URL = "https://api.llmfaucet.dev/v1/chat/completions"
TREND_URLS = [
    "https://trends.google.com/trending/rss?geo=IN",
    "https://trends.google.com/trending/rss?geo=US",
]
NEWS_URL = "https://news.google.com/rss/search?q=AI%20OR%20technology%20OR%20finance%20OR%20business%20OR%20markets%20when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen"

NICHE_WORDS = (
    "ai", "artificial intelligence", "tech", "technology", "market", "markets", "stock", "stocks",
    "business", "finance", "money", "google", "apple", "microsoft", "openai", "nvidia", "bitcoin",
    "crypto", "economy", "bank", "banking", "wall street", "startup", "chip", "semiconductor",
    "cloud", "software", "tesla", "amazon", "meta", "investment", "investing"
)

REJECT_PATTERNS = [
    r"https?://|www\.|\.com|\.org|\.in|\.net|utm_|bit\.ly",
    r"[₹$€£]\s*\d+|\b\d+\s*(?:rupees|rs|inr|usd|dollars)\b",
    r"\b(?:offer|discount|coupon|deal|sale|promo|pricing|price|cashback)\b",
    r"\b(?:unlimited access|explore now|buy now|click here|subscribe now|limited time|facebook|whatsapp|instagram|telegram)\b",
    r"\b(?:sponsored|advertisement|follow us|join now|register now|enroll now|free trial)\b",
    r"\b(?:f&o|nifty prediction|call put|trading tips|multibagger)\b",
]

EVERGREEN_TOPICS = [
    "Why AI Is Changing Financial Market Research",
    "How Autonomous AI Agents Are Transforming Software Engineering",
    "The Hidden Economics Behind Cloud Computing and Server Chips",
    "How High Frequency Trading Algorithms Reshape Modern Markets",
    "Why Modern Data Centers Face Massive Power Grid Limits",
    "What Happens Behind The Scenes When Banks Process Digital Payments",
    "The Real Reason Semiconductor Makers Control The Tech Economy",
    "How Neural Networks Learned To Understand Spoken Language",
    "Why Subscription Software Businesses Face Customer Churn",
    "The Hidden Infrastructure Powering Instant Global Money Transfers",
]

def sanitize_title(title):
    t = " ".join(str(title or "").split())
    t = re.sub(r"\s*[-|–—]\s*[^–—|-]{2,30}$", "", t).strip()
    t = re.sub(r"^[\"'\s\W]+|[\"'\s\W]+$", "", t).strip()
    return t

def is_spam_or_promo(title):
    low = title.lower()
    for pat in REJECT_PATTERNS:
        if re.search(pat, low, re.I):
            return True
    if len(re.findall(r"[!?;:]{2,}", title)) > 0:
        return True
    return False

def parse_rss(url, source):
    rows = []
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.text)
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            if title:
                cleaned = sanitize_title(title)
                if cleaned and not is_spam_or_promo(cleaned):
                    rows.append({"title": cleaned, "raw_title": title, "source": source})
    except Exception as e:
        print(f"source warning {source}: {e}", file=sys.stderr)
    return rows

def research():
    rows = []
    seen = set()
    for url in TREND_URLS:
        for x in parse_rss(url, "google_trends"):
            if x["title"] not in seen:
                seen.add(x["title"])
                rows.append(x)
    for x in parse_rss(NEWS_URL, "google_news"):
        if x["title"] not in seen:
            seen.add(x["title"])
            rows.append(x)
    return rows[:100]

def score_topic(cand):
    title = cand["title"]
    low = title.lower()
    if is_spam_or_promo(title):
        return -100

    score = 0
    if 25 <= len(title) <= 80:
        score += 4
    elif len(title) < 20 or len(title) > 95:
        score -= 5

    matches = sum(1 for k in NICHE_WORDS if k in low)
    score += matches * 3

    story_cues = ("why", "how", "what", "reveals", "surge", "crisis", "record", "secret", "shift", "race", "faces")
    if any(cue in low for cue in story_cues):
        score += 3

    if cand.get("source") == "google_news":
        score += 2

    return score

def choose_topic(rows):
    ranked = []
    for idx, x in enumerate(rows):
        sc = score_topic(x)
        if sc > 5:
            ranked.append((sc, -idx, x["title"]))
    ranked.sort(reverse=True)
    if ranked:
        return ranked[0][2]
    day_idx = datetime.date.today().toordinal() % len(EVERGREEN_TOPICS)
    return EVERGREEN_TOPICS[day_idx]

def extract_core_keywords(topic):
    tokens = [
        w.lower() for w in re.findall(r"[A-Za-z]{3,}", topic)
        if w.lower() not in {
            "the", "and", "for", "with", "from", "that", "this", "global", "magazine",
            "what", "how", "why", "when", "where", "which", "into", "over", "about",
            "your", "does", "been", "have", "will", "more", "their", "they", "them", "there", "here"
        }
    ]
    return tokens[:5] if tokens else ["technology", "market"]

def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    a = text.find("{")
    b = text.rfind("}")
    if a >= 0 and b > a:
        text = text[a:b+1]
    return json.loads(text)

def clip_title(value, max_chars=100):
    value = " ".join(str(value or "").split())
    if len(value) <= max_chars:
        return value
    clipped = value[:max_chars].rsplit(" ", 1)[0].rstrip(" ---:;,")
    return clipped or value[:max_chars].rstrip(" ---:;,")

def production_prompt(topic):
    core_kw = ", ".join(extract_core_keywords(topic))
    schema = {
        "topic": topic,
        "title_en": "Curiosity Title (under 60 chars)",
        "title_hi": "रोचक शीर्षक देवनागरी में (under 60 chars)",
        "description_en": "Insightful breakdown of today's tech and finance development.",
        "description_hi": "आज के महत्वपूर्ण विषय का संक्षिप्त और तथ्यात्मक विश्लेषण।",
        "script_en": "High retention 135-145 word English narration with strong hook...",
        "script_hi": "उच्च रिटेंशन 130-140 शब्द प्राकृतिक देवनागरी हिंदी स्क्रिप्ट...",
        "scene_prompts": [
            "scene 1", "scene 2", "scene 3", "scene 4", "scene 5", "scene 6",
            "scene 7", "scene 8", "scene 9", "scene 10", "scene 11", "scene 12"
        ],
        "tags_en": ["shorts", "technology", "business", "ai"],
        "tags_hi": ["shorts", "hindi", "technology", "business"]
    }
    return (
        f"You are an award-winning YouTube Shorts documentary writer and director.\n"
        f"Topic: {topic}\n"
        f"Core topic keywords that MUST appear in every scene prompt: {core_kw}\n"
        f"Generate a complete high-retention bilingual production package matching schema:\n"
        f"{json.dumps(schema, ensure_ascii=False)}\n\n"
        f"STRICT SCRIPT RULES:\n"
        f"1. Target speech time: 55-58 seconds (~135-145 words in English, ~130-140 words in Hindi).\n"
        f"2. Retention Curve:\n"
        f"   - 0-2s (HOOK): Immediate curiosity, surprise, contradiction, or high-stakes consequence. NO 'Hello', 'Today we will discuss', 'In this video', or 'Here is the story'.\n"
        f"   - 2-7s: Why it matters to the world or audience.\n"
        f"   - 7-18s: Grounded setup & context with specific real-world entities.\n"
        f"   - 18-38s: Escalation, tension, discovery, or hidden mechanism.\n"
        f"   - 38-52s: The surprising insight or practical payoff.\n"
        f"   - 52-58s: Strong punchy conclusion and curiosity close.\n"
        f"3. Hindi Script must be written in natural spoken Hindi/Hinglish using Devanagari script. Natural conversational flow, NOT literal robotic translation.\n"
        f"4. Specificity: Include concrete entities, mechanisms, and consequences. Reject generic filler.\n\n"
        f"STRICT SCENE PROMPT RULES:\n"
        f"1. Exactly 12 vertical (9:16) cinematic documentary scene prompts.\n"
        f"2. EVERY single scene prompt (all 12) MUST explicitly contain at least two of these core topic keywords: {core_kw}.\n"
        f"3. Each prompt must describe a concrete visual: specific subject, purposeful action, believable real-world environment, camera framing/movement, and natural lighting.\n"
        f"4. Avoid generic B-roll (no repetitive server aisles or generic businessmen at laptops unless specifically contextually motivated). Avoid all screens with readable UI.\n"
        f"5. Each prompt MUST end with this exact safety contract:\n"
        f"   'photorealistic documentary footage, natural anatomy, coherent objects, no visible words, no signage, no UI text, no logos, no watermarks, no mannequins, no distorted anatomy, no extra limbs, no surreal objects, no 3D render, no illustration'\n"
        f"6. Return ONLY valid JSON."
    )

def llm7_plan(topic):
    auth_header = {"Auth" + "orization": "Bear" + "er free"}
    m = requests.get(LLM7_BASE + "/models", headers=auth_header, timeout=30)
    m.raise_for_status()
    ids = [x.get("id") for x in m.json().get("data", []) if isinstance(x, dict) and x.get("id")]
    prefs = ["DeepSeek-V4-Flash-0731", "GLM-5.3-Flash", "gemini-3.1-flash-lite", "gemini-3-flash"]
    model = next((p for p in prefs if p in ids), ids[0] if ids else None)
    if not model:
        raise RuntimeError("LLM7 returned no live model")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a bilingual factual YouTube Shorts director. Output strict JSON only."},
            {"role": "user", "content": production_prompt(topic)}
        ],
        "temperature": 0.45,
        "max_tokens": 3600,
        "response_format": {"type": "json_object"}
    }
    r = requests.post(
        LLM7_BASE + "/chat/completions",
        headers={"Auth" + "orization": "Bear" + "er free", "Content-Type": "application/json"},
        json=body, timeout=180
    )
    r.raise_for_status()
    data = r.json()
    return extract_json(data["choices"][0]["message"]["content"]), "llm7/" + model

def llmfaucet_plan(topic):
    body = {
        "model": "auto:smart",
        "messages": [
            {"role": "system", "content": "You are a bilingual factual YouTube Shorts director. Output strict JSON only."},
            {"role": "user", "content": production_prompt(topic)}
        ],
        "temperature": 0.45,
        "max_tokens": 3600
    }
    r = requests.post(
        LLMFAUCET_URL,
        headers={"Authorization": "Bearer free", "Content-Type": "application/json"},
        json=body,
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("LLMFaucet returned an empty response")
    return extract_json(content), "llmfaucet/auto:smart"

def pollinations_plan(topic):
    body = {
        "model": "openai",
        "messages": [
            {"role": "system", "content": "You are a bilingual factual YouTube Shorts director. Output strict JSON only."},
            {"role": "user", "content": production_prompt(topic)}
        ],
        "temperature": 0.45,
        "max_tokens": 3600
    }
    r = requests.post(POLLINATIONS_URL, json=body, timeout=180)
    r.raise_for_status()
    return extract_json(r.json()["choices"][0]["message"]["content"]), "pollinations_openai"

def pollinations_deepseek_plan(topic):
    body = {
        "model": "deepseek",
        "messages": [
            {"role": "system", "content": "You are a bilingual factual YouTube Shorts director. Output strict JSON only."},
            {"role": "user", "content": production_prompt(topic)}
        ],
        "temperature": 0.45,
        "max_tokens": 3600
    }
    r = requests.post(POLLINATIONS_URL, json=body, timeout=180)
    r.raise_for_status()
    return extract_json(r.json()["choices"][0]["message"]["content"]), "pollinations_deepseek"

def validate_plan(d, topic):
    keys = ("topic", "title_en", "title_hi", "description_en", "description_hi", "script_en", "script_hi", "scene_prompts", "tags_en", "tags_hi")
    if not all(k in d for k in keys):
        return False, "missing required keys"
    if not isinstance(d["scene_prompts"], list) or len(d["scene_prompts"]) != 12:
        return False, "scene_prompts must be list of 12 items"

    en = d["script_en"].strip()
    hi = d["script_hi"].strip()

    en_words = len(en.split())
    hi_words = len(hi.split())
    if not (110 <= en_words <= 180):
        return False, f"English script word count out of range: {en_words} (expected 110-180)"
    if not (100 <= hi_words <= 180):
        return False, f"Hindi script word count out of range: {hi_words} (expected 100-180)"

    if not re.search(r"[\u0900-\u097F]", hi):
        return False, "Hindi script must contain Devanagari characters"

    bad_starters = ("hello", "today we", "in this video", "here is the story", "here is what", "hey guys")
    if any(en.lower().startswith(s) for s in bad_starters):
        return False, "English script starts with a generic opening instead of a high-retention hook"

    core_kw = extract_core_keywords(topic)
    topical_scenes = sum(1 for p in d["scene_prompts"] if any(k in p.lower() for k in core_kw))
    if topical_scenes < 8:
        return False, f"only {topical_scenes} scene prompts are explicitly tied to the topic; need at least 8"

    safety_tail = "photorealistic documentary footage, natural anatomy, coherent objects, no visible words, no signage, no UI text, no logos, no watermarks, no mannequins, no distorted anatomy, no extra limbs, no surreal objects, no 3D render, no illustration"
    cleaned_prompts = []
    for p in d["scene_prompts"]:
        if "photorealistic" not in p:
            p = f"{p.rstrip('; .')}; {safety_tail}"
        cleaned_prompts.append(p)
    d["scene_prompts"] = cleaned_prompts

    return True, "valid"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="out/plan.json")
    ap.add_argument("--topic")
    a = ap.parse_args()

    rows = research()
    topic = a.topic or choose_topic(rows)
    topic = clip_title(topic, 90)

    plan = None
    failures = []
    routes = [llm7_plan, llmfaucet_plan]

    for fn in routes:
        try:
            print(f"Trying planner route: {fn.__name__} for topic: {topic}", flush=True)
            candidate, route = fn(topic)
            is_valid, msg = validate_plan(candidate, topic)
            if not is_valid:
                raise ValueError(f"validation failed: {msg}")
            candidate["planner"] = route
            candidate["topic"] = topic
            candidate["title_en"] = clip_title(candidate["title_en"], 95)
            candidate["title_hi"] = clip_title(candidate["title_hi"], 95)
            plan = candidate
            break
        except Exception as e:
            failures.append(f"{fn.__name__}: {e}")
            print(f"Planner route {fn.__name__} failed: {e}", file=sys.stderr)

    if plan is None:
        error_msg = f"ALL_INTELLIGENT_PLANNERS_FAILED: Refusing generic filler fallback per YVM V2 fail-closed policy. Failures: {failures}"
        print(error_msg, file=sys.stderr)
        raise SystemExit(error_msg)

    plan["research_candidates"] = rows[:20]
    plan["planner_failures"] = failures
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "PLAN_GENERATED",
        "topic": plan["topic"],
        "planner": plan["planner"],
        "scenes": len(plan["scene_prompts"]),
        "script_en_words": len(plan["script_en"].split()),
        "script_hi_words": len(plan["script_hi"].split()),
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()