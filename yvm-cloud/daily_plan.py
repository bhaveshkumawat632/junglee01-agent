#!/usr/bin/env python3
import argparse, json, re, sys, xml.etree.ElementTree as ET
from pathlib import Path
import requests

TRENDS = [
    "https://trends.google.com/trending/rss?geo=IN",
    "https://trends.google.com/trending/rss?geo=US",
]
TEXT_URL = "https://text.pollinations.ai/openai"

def get_trends():
    rows = []
    seen = set()
    for url in TRENDS:
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0"})
            r.raise_for_status()
            root = ET.fromstring(r.text)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                if title and title not in seen:
                    seen.add(title)
                    rows.append({"title": title})
        except Exception as e:
            print("trend source warning:", url, e, file=sys.stderr)
    return rows[:40]

def choose(rows):
    keys = ("ai","tech","market","stock","business","finance","money","google","apple","microsoft","openai","nvidia","bitcoin","crypto","economy","bank","wall street")
    ranked = []
    for x in rows:
        score = sum(2 for k in keys if k in x["title"].lower())
        ranked.append((score, x["title"]))
    ranked.sort(reverse=True)
    return ranked[0][1] if ranked else "A surprising technology and money story people are discussing today"

def public_llm(topic):
    schema = {
        "topic":"...", "title_en":"...", "title_hi":"...",
        "description_en":"...", "description_hi":"...",
        "script_en":"...", "script_hi":"...",
        "scene_prompts":["eight cinematic 9:16 prompts"],
        "tags_en":["..."], "tags_hi":["..."]
    }
    prompt = (
        "Create a complete YouTube Shorts production plan about: " + topic + "\\n"
        "Goal: factual high-retention monetization-friendly 55-60 second vertical short for India and global audiences. "
        "Return ONLY valid JSON using this schema: " + json.dumps(schema) + ". "
        "English and Hindi scripts must convey the same facts naturally. Hook in first 2 seconds. "
        "Give exactly 8 realistic cinematic 9:16 visual prompts, no readable text/logos/copyrighted characters. "
        "Do not invent precise claims. End with a short curiosity line."
    )
    body = {
        "model":"openai",
        "messages":[
            {"role":"system","content":"You are a concise bilingual YouTube Shorts producer. Output strict JSON only."},
            {"role":"user","content":prompt}
        ],
        "temperature":0.65,
        "max_tokens":2400
    }
    r = requests.post(TEXT_URL, json=body, timeout=180)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^\\x60\\x60\\x60(?:json)?\\s*|\\s*\\x60\\x60\\x60$", "", content, flags=re.I)
    return json.loads(content)

def fallback(topic):
    en = (
        "What if the headline everyone is seeing about " + topic + " is only half the story? "
        "In less than a minute, here is the useful part. Separate the headline from the actual event. "
        "Then ask who is affected: users, investors, companies, or everyday buyers. "
        "Watch what changes next because the first reaction is often louder than the long-term impact. "
        "Do not chase a viral claim blindly. Check the original source, compare reliable reports, "
        "and focus on what can actually change your decision. Save this topic and compare tomorrow's update with today's facts."
    )
    hi = (
        topic + " की जो headline हर जगह दिख रही है, हो सकता है वह पूरी कहानी न हो। "
        "एक मिनट में काम की बात समझिए। पहले headline और असली घटना को अलग कीजिए। "
        "फिर देखिए असर किस पर है—users, investors, companies या आम buyers पर। "
        "अगले बदलाव पर ध्यान दीजिए क्योंकि पहली reaction अक्सर long-term impact से ज्यादा तेज होती है। "
        "किसी viral claim को blindly follow मत कीजिए। Original source देखिए, reliable reports compare कीजिए "
        "और सिर्फ उस जानकारी पर focus कीजिए जो आपके decision को सच में बदल सकती है।"
    )
    scenes = [
        "cinematic realistic vertical breaking-news atmosphere, dramatic practical lighting, no text",
        "close-up of a smartphone news feed reflected in eyes, realistic, vertical",
        "modern finance and technology workspace with abstract charts, no readable text, vertical",
        "people reacting to breaking news in an office, documentary realism, vertical",
        "macro shot of market movement on screens, no logos, cinematic vertical",
        "analyst comparing multiple sources on laptop and phone, realistic hands, vertical",
        "calm decision-making scene with notebook and screens, premium lighting, vertical",
        "cinematic closing shot of city and technology screens at dusk, vertical, no text"
    ]
    return {
        "topic":topic,
        "title_en":topic + ": What Actually Matters",
        "title_hi":topic + ": असली बात क्या है?",
        "description_en":"A quick breakdown of what matters behind today's headline.",
        "description_hi":"आज की headline के पीछे की काम की बात, 60 seconds में.",
        "script_en":en, "script_hi":hi, "scene_prompts":scenes,
        "tags_en":["shorts","news","technology","money"],
        "tags_hi":["shorts","hindi","news","technology"]
    }

def valid(d):
    req = ["topic","title_en","title_hi","description_en","description_hi","script_en","script_hi","scene_prompts","tags_en","tags_hi"]
    return all(k in d for k in req) and isinstance(d["scene_prompts"], list) and len(d["scene_prompts"]) >= 8 and len(d["script_en"]) > 250 and len(d["script_hi"]) > 200

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="out/plan.json")
    ap.add_argument("--topic")
    a = ap.parse_args()
    rows = get_trends()
    topic = a.topic or choose(rows)
    try:
        plan = public_llm(topic)
        if not valid(plan):
            raise ValueError("planner validation failed")
        plan["planner"] = "pollinations_public"
    except Exception as e:
        print("public planner fallback:", e, file=sys.stderr)
        plan = fallback(topic)
        plan["planner"] = "deterministic_fallback"
    plan["trend_candidates"] = rows[:10]
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    print(json.dumps({"topic":plan["topic"],"planner":plan["planner"],"scenes":len(plan["scene_prompts"])}, ensure_ascii=False))

if __name__ == "__main__":
    main()
