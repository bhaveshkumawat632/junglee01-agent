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
        + "and a natural Hindi narration conveying the same verified points; hook within first 2 seconds; "
        + "exactly 12 cinematic realistic 9:16 scene prompts, each intended for about 5 seconds; "
        + "no readable text, logos, copyrighted characters, fabricated quotes or unsupported precise numbers. "
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

def fallback_plan(topic):
    en=(
        f"Here is the useful story behind {topic}. The headline may move quickly, so focus on what is actually known. "
        "Start with the confirmed event, then ask who is affected and what could change next. "
        "For technology and markets, the first reaction is often louder than the long-term impact. "
        "That is why one viral post is not enough. Check the original announcement, compare reliable reporting, "
        "and separate facts from predictions. The practical takeaway is simple: understand the mechanism before "
        "making a money, technology, or business decision. The next update matters more than the first rumor."
    )
    hi=(
        f"{topic} के पीछे की काम की बात समझिए। Headline तेजी से बदल सकती है, इसलिए पहले confirmed event पर focus करें। "
        "फिर देखें असर किस पर पड़ेगा और अगला बदलाव क्या हो सकता है। Technology और markets में पहली reaction अक्सर "
        "long-term impact से ज्यादा तेज होती है। इसलिए एक viral post पर भरोसा मत कीजिए। Original announcement देखें, "
        "reliable reports compare करें और facts को predictions से अलग रखें। Practical lesson यही है: किसी money, "
        "technology या business decision से पहले mechanism समझिए। अगला verified update पहली rumor से ज्यादा important है।"
    )
    motifs=[
        f"cinematic vertical documentary opening representing {topic}, realistic practical lighting, no text",
        "close-up of smartphone and laptop news research, realistic hands, shallow depth of field, vertical",
        "modern technology office with abstract data screens, no readable text or logos, vertical",
        "financial district morning street scene, documentary realism, vertical composition",
        "analyst reviewing several information sources, natural human motion, vertical",
        "macro view of abstract market charts on CRT and modern displays, no readable text, vertical",
        "semiconductor and server hardware detail, cinematic macro shot, vertical",
        "business meeting with natural expressions and realistic anatomy, vertical",
        "city infrastructure and data center exterior at dusk, cinematic vertical",
        "person calmly taking notes beside laptop, premium natural lighting, vertical",
        "wide shot of active modern office with subtle camera motion, realistic, vertical",
        "cinematic closing city skyline and technology reflections, no text, vertical",
    ]
    return {
        "topic":topic,
        "title_en":topic+" — What Actually Matters",
        "title_hi":topic+" — असली बात क्या है?",
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
