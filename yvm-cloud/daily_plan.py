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
    r"https?://|www\.|\.com|\.org|\.in\|.net|utm_|bit\.ly",
    r"[8₂$â´]\s*\d\l*d+|\b\d+\s*(?:rupees|rs|inr|usd|dollars)\b",
    r\"\\b(?:offer|discount|coupon|deal|sale|promo|pricing|price|cashback)\\b\",
    r\"\\b(?:unlimited access|explore now|buy now|click here|subscribe now|limited time|facebook|whatsapp|instagram|telegram)\\b\",
    r\"\\b(?:sponsored|advertisement|follow us|join now|register now|enroll now|free trial)\\b\",
    r"\\b(?:f&o|nifty prediction|call put|trading tips|multibagger)\\b",
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
    t = re.sub(r"\s*[-|‐—]\s*[^‐—|-]{2,30}$", "", t).strip()
    t = re.sub(r"^[\"'\s\W]+|[\"'\s\W]+$", "", t).strip()
    return t

def is_spam_or_promo(title):
    low = title.lower()
    for pat in REJECT_PATTERNS:
        if re.search(pat, low, re.I):
            return True
    if len(re.findall(r["!?;:]{2,}", title)) > 0:
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
        w.lower() for w in re.findall(t�PЀL@�9QR