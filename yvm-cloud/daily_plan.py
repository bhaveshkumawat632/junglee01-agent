#!/usr/bin/env python3
import argparse
import datetime
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

LLM7_BASE = "https://api.llm7.io/v1"
POLLINATIONS_URL = "https://text.pollinations.ai/openai"
TREND_URLS = [
    "https://trends.google.com/trending/rss?geo=IN",
    "https://trends.google.com/trending/rss?geo=US",
]
NEWS_URL = "https://news.google.com/rss/search?q=AI%20OR%20technology%20OR%20finance%20OR%20business%20OR%20markets%20when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen"

NICHE_WORDS = (
    "ai","artificial intelligence","tech","technology","market","markets","stock","stocks",
    "business","finance","money","google","apple","microsoft","openai","nvidia","bitcoin",
    "crypto","economy","bank","banking","wall street","startup","chip","semiconductor",
    "cloud","software","tesla","amazon","meta","investment","investing"
)

EVERGREEN = [
    "How AI agents are changing everyday work",
    "What most people misunderstand about compound investing",
    "Why chip companies matter to the AI boom",
    "How digital payments changed the way money moves",
    "The hidden economics behind subscription businesses",
    "What happens behind the scenes when markets move fast",
    "Why cloud computing became the backbone of modern apps",
    "How Wall Street traders managed information before modern apps",
    "Why data centers became strategic infrastructure",
    "The business model behind free internet services",
]

def parse_rss(url, source):
    rows=[]
    try:
        r=requests.get(url,timeout=25,headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        root=ET.fromstring(r.text)
        for item in root.findall(".//item"):
            title=(item.findtext("title") or "").strip()
            if title:
                rows.append({"title":title,"source":source})
    except Exception as e:
        print(f"source warning {source}: {e}",file=sys.stderr)
    return rows

def research():
    rows=[]
    seen=set()
    for url in TREND_URLS:
        for x in parse_rss(url,"google_trends"):
            if x["title"] not in seen:
                seen.add(x["title"]); rows.append(x)
    for x in parse_rss(NEWS_URL,"google_news"):
        if x["title"] not in seen:
            seen.add(x["title"]); rows.append(x)
    return rows[:100]

def choose_topic(rows):
    ranked=[]
    for idx,x in enumerate(rows):
        low=x["title"].lower()
        score=sum(3 for k in NICHE_WORDS if k in low)
        if x["source"]=="google_news":
            score+=1
        ranked.append((score,-idx,x["title"]))
    ranked.sort(reverse=True)
    if ranked and ranked[0][0] > 1:
        return ranked[0][2]
    return EVERGREEN[datetime.date.today().toordinal() % len(EVERGREEN)]

def extract_json(text):
    text=text.strip()
    text=re.sub(r"^\x60\x60\x60(?:json)?\s*|\s*\x60\x60\x60$","",text,flags=re.I)
    a=text.find("{"); b=text.rfind("}")
    if a>=0 and b>a:
        text=text[a:b+1]
    return json.loads(text)

def production_prompt(topic):
    schema={
        "topic":"...",
        "title_en":"...",
        "title_hi":"...",
        "description_en":"...",
        "description_hi":"...",
        "script_en":"...",
        "script_hi":"...",
        "scene_prompts":["scene 1","scene 2","scene 3","scene 4","scene 5","scene 6","scene 7","scene 8","scene 9","scene 10","scene 11","scene 12"],
        "tags_en":["..."],
        "tags_hi":["..."]
    }
    return (
        "Create a complete bilingual YouTube Shorts production package about this topic: "
        + topic + "\n"
        + "Return ONLY valid JSON matching: " + json.dumps(schema) + "\n"
        + "Requirements: factual, high-retention, monetization-friendly; 55-60 second English narration "
        + "and a natural Hindi narration conveying the same verified points; Hindi title must contain Devanagari; "
        + "hook within first 2 seconds; exactly 12 cinematic realistic 9:16 scene prompts, each intended for about 5 seconds. "
        + "Every scene prompt must explicitly repeat the core topic entities/keywords (company, market, technology, event, or named subject) so automated topical QC can verify relevance. " + "Every scene prompt must be topic-specific and describe a grounded documentary shot with a concrete subject, action, environment, "
        + "camera framing/movement, lens feel, and lighting. Prefer real locations, believable props, medium/wide or over-the-shoulder human shots, "
        + "and visually distinct scenes that advance the narration. Avoid front-facing screens, posters, signs, dashboards, documents, or any surface "
        + "that invites generated lettering; if a display is unavoidable, keep it defocused with no legible interface. Human shots must use normal clothing "
        + "and natural anatomy; avoid mannequins, plastic skin, fashion poses, exposed bodies, close-up fingers, or awkward hand interactions. "
        + "Each prompt must explicitly end with: 'photorealistic documentary footage, natural anatomy, coherent objects, no visible words, no signage, "
        + "no UI text, no logos, no watermarks, no mannequins, no distorted anatomy, no extra limbs, no surreal objects, no 3D render, no illustration'. "
        + "Do not use generic filler b-roll that could fit any topic. "
        + "No copyrighted characters, fabricated quotes or unsupported precise numbers. "
        + "If the headline is uncertain, frame it cautiously instead of inventing facts. "
        + "End with a brief useful curiosity/engagement line, not clickbait spam."
    )

def llm7_plan(topic):
    h={"Authorization":"Bearer free"}
    m=requests.get(LLM7_BASE+"/models",headers=h,timeout=30)
    m.raise_for_status()
    ids=[x.get("id") for x in m.json().get("data",[]) if isinstance(x,dict) and x.get("id")]
    prefs=["DeepSeek-V4-Flash-0731","GLM-5.3-Flash","gemini-3.1-flash-lite","gemini-3-flash"]
    model=next((p for p in prefs if p in ids), ids[0] if ids else None)
    if not model:
        raise RuntimeError("LLM7 returned no live model")
    body={
        "model":model,
        "messages":[
            {"role":"system","content":"You are a bilingual factual YouTube Shorts producer. Return strict JSON only."},
            {"role":"user","content":production_prompt(topic)}
        ],
        "temperature":0.45,
        "max_tokens":3200
    }
    r=requests.post(
        LLM7_BASE+"/chat/completions",
        headers={"Authorization":"Bearer free","Content-Type":"application/json"},
        json=body,timeout=180
    )
    r.raise_for_status()
    data=r.json()
    return extract_json(data["choices"][0]["message"]["content"]), "llm7/"+model

def pollinations_plan(topic):
    body={
        "model":"openai",
        "messages":[
            {"role":"system","content":"You are a bilingual factual YouTube Shorts producer. Return strict JSON only."},
            {"role":"user","content":production_prompt(topic)}
        ],
        "temperature":0.5,
        "max_tokens":3200
    }
    r=requests.post(POLLINATIONS_URL,json=body,timeout=180)
    r.raise_for_status()
    return extract_json(r.json()["choices"][0]["message"]["content"]), "pollinations_public"

def clip_title(value, max_chars=100):
    value=" ".join(str(value or "").split())
    if len(value) <= max_chars:
        return value
    clipped=value[:max_chars].rsplit(" ",1)[0].rstrip(" -–—:;,")
    return clipped or value[:max_chars].rstrip(" -–—:;,")

def fallback_plan(topic):
    en=(
        f"Here is the useful story behind {topic}. The headline may move quickly, so focus first on what is actually known. "
        "Identify the confirmed event, who announced it, who could be affected, and which details are still uncertain. "
        "Then look at the mechanism: how could this change technology, money, business, customers, or markets in practice? "
        "The first online reaction is often louder than the long-term impact, so one viral post is never enough evidence. "
        "Check the original announcement, compare several reliable reports, and separate verified facts from forecasts. "
        "Watch for the next measurable signal, such as a product release, filing, price change, adoption number, or official update. "
        "That second piece of evidence often tells you more than the first headline. "
        "The practical takeaway is simple: understand what changed, why it matters, and what evidence would confirm the story before making a decision. "
        "Stay curious, but let verified updates lead the conclusion."
    )
    hi=(
        f"{topic} के पीछे की असली काम की बात समझिए। Headline तेजी से बदल सकती है, इसलिए सबसे पहले यह देखें कि confirmed event क्या है, "
        "इसे किसने announce किया और कौन-सी बातें अभी भी uncertain हैं। फिर mechanism समझिए: इसका असर technology, money, business, "
        "customers या markets पर practically कैसे पड़ सकता है? Online पहली reaction अक्सर long-term impact से ज्यादा तेज होती है, "
        "इसलिए एक viral post को evidence मत मानिए। Original announcement देखें, कई reliable reports compare करें और verified facts को "
        "forecasts से अलग रखें। इसके बाद अगला measurable signal देखें—जैसे official update, product release, filing, price change, "
        "adoption number या कोई confirmed result। अक्सर यही दूसरा signal पहली headline से ज्यादा useful होता है। "
        "Practical lesson साफ है: decision लेने से पहले समझिए कि क्या बदला, क्यों matter करता है और कौन-सा evidence इस story को confirm करेगा। "
        "Curious रहिए, लेकिन conclusion verified updates के आधार पर बनाइए।"
    )
    quality_tail="photorealistic documentary footage, natural anatomy, coherent objects, no visible words, no signage, no UI text, no logos, no watermarks, no mannequins, no distorted anatomy, no extra limbs, no surreal objects, no 3D render, no illustration"
    motifs=[
        f"Vertical documentary establishing shot for {topic}: real financial district at blue hour, office workers entering a modern glass building, slow stabilized push-in, 35mm lens feel, practical city lighting, believable architecture; {quality_tail}",
        f"Vertical over-the-shoulder research shot tied to {topic}: analyst in normal business clothing comparing printed notes and a laptop whose screen is angled away and defocused, subtle handheld camera drift, 50mm lens feel, soft window light; {quality_tail}",
        f"Vertical AI-in-finance infrastructure shot for {topic}: real server racks and cooling aisles inside a modern data center, technicians seen from behind at a distance, slow lateral dolly, 35mm lens feel, cool practical lighting; {quality_tail}",
        f"Vertical Wall Street context shot for {topic}: busy financial-district sidewalk with suited workers crossing between stone-and-glass office buildings, natural pedestrian motion, stabilized street-level tracking shot, 35mm lens feel, morning light; {quality_tail}",
        f"Vertical workplace-anxiety visual for {topic}: small finance team in a conference room listening to a colleague present without visible screens or boards, natural expressions, medium-wide composition, slow slider move, 50mm lens feel, neutral office lighting; {quality_tail}",
        f"Vertical market-operations shot for {topic}: close view of hands placing color-coded paper cards and physical tokens on a clean desk to represent changing workflows, no screens and no writing, controlled overhead camera move, 50mm lens feel, soft practical lighting; {quality_tail}",
        f"Vertical technology investment shot for {topic}: macro details of real server components, network switches, cooling fans and cable management, slow rack focus, 85mm macro lens feel, dramatic but realistic practical light; {quality_tail}",
        f"Vertical human-work shot for {topic}: two finance professionals in normal business attire discussing a printed chart whose markings are out of focus, waist-up framing, realistic faces and hands kept relaxed, slow handheld documentary motion, 50mm lens feel; {quality_tail}",
        f"Vertical corporate infrastructure shot for {topic}: exterior of a real office tower at dusk with workers visible only as small silhouettes through windows, slow tilt upward, 35mm lens feel, natural city illumination; {quality_tail}",
        f"Vertical decision-making shot for {topic}: analyst seen from behind writing simple non-readable marks in a notebook beside a closed laptop, medium shot, gentle push-in, 50mm lens feel, warm window light; {quality_tail}",
        f"Vertical modern-office transition for {topic}: active open-plan finance office with people moving naturally in the background, no visible screens facing camera, wide composition, slow gimbal move, 35mm lens feel, balanced daylight; {quality_tail}",
        f"Vertical closing shot for {topic}: real financial skyline at sunset seen from street level with moving traffic reflections on glass, slow stabilized pull-back, 35mm lens feel, realistic atmospheric light; {quality_tail}",
    ]
    title_topic=clip_title(topic, 68)
    return {
        "topic":topic,
        "title_en":clip_title(title_topic+" — What Actually Matters"),
        "title_hi":clip_title(title_topic+" — असली बात क्या है?"),
        "description_en":"A concise factual breakdown of the technology, money, or business angle behind today's topic.",
        "description_hi":"आज के topic के technology, money या business angle की concise factual breakdown.",
        "script_en":en,
        "script_hi":hi,
        "scene_prompts":motifs,
        "tags_en":["shorts","technology","business","finance","ai"],
        "tags_hi":["shorts","hindi","technology","business","finance"],
    }

def valid(d):
    keys=("topic","title_en","title_hi","description_en","description_hi","script_en","script_hi","scene_prompts","tags_en","tags_hi")
    return (
        all(k in d for k in keys)
        and isinstance(d["scene_prompts"],list)
        and len(d["scene_prompts"]) == 12
        and len(d["script_en"]) > 280
        and len(d["script_hi"]) > 220
    )

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="out/plan.json")
    ap.add_argument("--topic")
    a=ap.parse_args()
    rows=research()
    topic=a.topic or choose_topic(rows)

    plan=None
    failures=[]
    for fn in (llm7_plan,pollinations_plan):
        try:
            candidate,route=fn(topic)
            if not valid(candidate):
                raise ValueError("plan failed structural validation")
            candidate["planner"]=route
            plan=candidate
            break
        except Exception as e:
            failures.append(f"{fn.__name__}: {e}")
            print(failures[-1],file=sys.stderr)

    if plan is None:
        plan=fallback_plan(topic)
        plan["planner"]="deterministic_fallback"

    plan["research_candidates"]=rows[:20]
    plan["planner_failures"]=failures
    out=Path(a.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    print(json.dumps({
        "topic":plan["topic"],
        "planner":plan["planner"],
        "scenes":len(plan["scene_prompts"]),
        "research_candidates":len(rows)
    },ensure_ascii=False))

if __name__=="__main__":
    main()
