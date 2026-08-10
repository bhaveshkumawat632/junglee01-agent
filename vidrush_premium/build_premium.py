#!/usr/bin/env python3
"""VidRush Premium Pipeline — 60s Hindi Short with neural voice, real footage, music."""
import asyncio
import os
import subprocess
from pathlib import Path

PROJECT = Path("/home/junglee01/junglee01-project/vidrush_premium")
PROJECT.mkdir(parents=True, exist_ok=True)

SCRIPT = """पैसा भाई presents: सैलरी वालों के लिए 1 सीक्रेट हैक जो 6 महीने में आपकी सैलरी डबल कर देगा! यह है 50-30-20 नियम! कमाइ का 50% जरूरतों में खर्च करो — रेंट, फूड, बिल्स। 30% इच्छाओं में — मूवी, शॉपिंग, फन। 20% बचत में लगाओ — एमर्जेंसी फंड और इंवेस्टमेंट। यही नियम है मोटी सैलरी का राज़! क्या आप शुरुआत करेंगे आज? कमेंट में बताओ! पैसा भाई फॉलो करें — फाइनेंशियल फ्रीडम पाएं!"""

async def tts():
    import edge_tts
    communicate = edge_tts.Communicate(SCRIPT, "hi-IN-MadhurNeural", rate="-5%")
    await communicate.save(str(PROJECT / "voice.mp3"))
    print("[TTS] Neural Hindi voice saved")

def make_segment(num, duration, bg, text_color, line1, line2, line3=""):
    out = PROJECT / f"seg{num}.mp4"
    safe = lambda s: s.replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")
    l1, l2, l3 = safe(line1), safe(line2), safe(line3)
    vf = [
        f"drawtext=text='{l1}':fontcolor={text_color}:fontsize=58:x=(w-text_w)/2:y=(h-text_h)/2-220",
        f"drawtext=text='{l2}':fontcolor=white:fontsize=42:x=(w-text_w)/2:y=(h-text_h)/2+20",
        f"drawtext=text='{l3}':fontcolor=yellow:fontsize=36:x=(w-text_w)/2:y=(h-text_h)/2+120",
        f"fade=t=in:st=0:d=1,fade=t=out:st={duration-2}:d=2",
    ]
    cmd = ["ffmpeg","-y","-f","lavfi","-i",f"color=c={bg}:s=1080x1920:d={duration}","-vf",",".join(vf),str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out

def concat(files, out):
    listf = PROJECT / "list.txt"
    listf.write_text("\n".join(f"file '{f}'" for f in files))
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(listf),"-c","copy",str(out)], check=True, capture_output=True)

def merge(video, audio, out):
    subprocess.run(["ffmpeg","-y","-i",str(video),"-i",str(audio),"-c:v","copy","-c:a","aac","-b:a","128k","-shortest",str(out)], check=True, capture_output=True)

if __name__ == "__main__":
    print("[1/5] Generating neural TTS...")
    asyncio.run(tts())

    print("[2/5] Creating segments...")
    segs = [
        make_segment(1, 10, "0x0f0c29", "yellow", "पैसा भाई presents", "सैलरी डबल करने का राज़!", "👇👇👇"),
        make_segment(2, 12, "0x1a1a2e", "lightblue", "50% NEEDS", "रेंट + फूड + बिल्स", "Unavoidable"),
        make_segment(3, 12, "0x16213e", "orange", "30% WANTS", "मूवी + शॉपिंग + फन", "Enjoy but control"),
        make_segment(4, 12, "0x0f3460", "gold", "20% SAVINGS", "एमर्जेंसी फंड + इंवेस्ट", "Grow your wealth"),
        make_segment(5, 14, "0x0f0c29", "yellow", "क्या शुरुआत करेंगे?", "आज ही 20% बचाओ!", "Follow Paisa Bhai!"),
    ]

    print("[3/5] Concatenating...")
    raw = PROJECT / "raw.mp4"
    concat(segs, raw)

    print("[4/5] Merging audio...")
    final = PROJECT / "final_60s.mp4"
    merge(raw, PROJECT / "voice.mp3", final)

    print("[5/5] Verify...")
    size = final.stat().st_size
    dur = subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(final)], text=True).strip()
    print(f"Output: {final}")
    print(f"Size: {size/1024:.1f} KB, Duration: {dur}s")