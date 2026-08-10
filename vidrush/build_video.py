#!/usr/bin/env python3
"""VidRush Production Pipeline — 60-second Hindi YouTube Short."""
import os
import subprocess
import textwrap
from pathlib import Path

PROJECT = Path("/home/junglee01/junglee01-project/vidrush")
PROJECT.mkdir(parents=True, exist_ok=True)

SCRIPT = """पैसा भाई presents: सैलरी वालों के लिए 1 सीक्रेट हैक
जो 6 महीने में आपकी सैलरी डबल कर देगा!
यह है 50-30-20 नियम!
कमाइ का 50% जरूरतों में खर्च करो — रेंट, फूड, बिल्स।
30% इच्छाओं में — मूवी, शॉपिंग, फन।
20% बचत में लगाओ — एमर्जेंसी फंड + इंवेस्टमेंट।
यही नियम है मोटी सैलरी का राज़!
क्या आप शुरुआत करेंगे आज?
कमेंट में बताओ!
पैसा भाई फॉलो करें — फाइनेंशियल फ्रीडम पाएं!"""

SEGMENTS = [
    (0, 8, "0x0f0c29", "yellow", "पैसा भाई presents", "सैलरी डबल करने का राज़!", "👇👇👇"),
    (8, 20, "0x1a1a2e", "lightblue", "50% NEEDS", "रेंट + फूड + बिल्स", " unavoidable"),
    (20, 32, "0x16213e", "orange", "30% WANTS", "मूवी + शॉपिंग + फन", "Enjoy but control"),
    (32, 44, "0x0f3460", "gold", "20% SAVINGS", "एमर्जेंसी फंड", "Invest + Grow"),
    (44, 60, "0x0f0c29", "yellow", "क्या शुरुआत करेंगे?", "आज ही 20% बचाओ!", "Follow Paisa Bhai!"),
]

def make_segment(idx, start, duration, bg, text_color, line1, line2, extra=""):
    out = PROJECT / f"seg{idx}.mp4"
    safe = lambda s: s.replace(":", "\\:").replace("'", "\\'")
    l1 = safe(line1)
    l2 = safe(line2)
    ex = safe(extra)
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={bg}:s=1080x1920:d={duration}",
        "-vf",
        f"drawtext=text='{l1}':fontcolor={text_color}:fontsize=60:x=(w-text_w)/2:y=(h-text_h)/2-180,"
        f"drawtext=text='{l2}':fontcolor=white:fontsize=44:x=(w-text_w)/2:y=(h-text_h)/2+20,"
        f"drawtext=text='{ex}':fontcolor=yellow:fontsize=52:x=(w-text_w)/2:y=(h-text_h)/2+140,"
        f"fade=t=in:st=0:d=1,fade=t=out:st={duration-2}:d=2",
        str(out)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out

def concat_segments(files, out):
    list_file = PROJECT / "concat.txt"
    list_file.write_text("\n".join(f"file '{f}'" for f in files))
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(out)
    ], check=True, capture_output=True)

def add_audio(video, audio, out):
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video), "-i", str(audio),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-shortest", str(out)
    ], check=True, capture_output=True)

print("[1/5] Generating segments...")
seg_files = []
for idx, (_, dur, bg, tc, l1, l2, ex) in enumerate(SEGMENTS, 1):
    p = make_segment(idx, _, dur, bg, tc, l1, l2, ex)
    seg_files.append(p)
    print(f"  seg{idx}.mp4 {dur}s")

print("[2/5] Concatenating video...")
raw = PROJECT / "raw.mp4"
concat_segments(seg_files, raw)

print("[3/5] Generating TTS...")
audio = PROJECT / "voice.mp3"
# Use gTTS with Hindi
from gtts import gTTS
tts = gTTS(text=SCRIPT, lang='hi', slow=False)
tts.save(str(audio))

print("[4/5] Merging audio...")
final = PROJECT / "final_60s.mp4"
add_audio(raw, audio, final)

print("[5/5] Verify...")
import os
size = os.path.getsize(final)
print(f"Output: {final}")
print(f"Size: {size/1024:.1f} KB")
subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)], check=True, capture_output=True)
