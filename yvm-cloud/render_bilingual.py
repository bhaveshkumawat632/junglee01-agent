#!/usr/bin/env python3
import argparse
import re
import subprocess
import textwrap
from pathlib import Path

def run(cmd):
    print("+"," ".join(map(str,cmd)),flush=True)
    subprocess.run([str(x) for x in cmd],check=True)

def tts(text, voice, audio_out, subtitle_out):
    run([
        "edge-tts",
        "--voice",voice,
        "--text",text,
        "--write-media",str(audio_out),
        "--write-subtitles",str(subtitle_out),
    ])

def wrap_srt(path, width=34):
    """Wrap caption text without changing Edge TTS timing blocks."""
    raw=Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        raise SystemExit(f"Subtitle generation failed: empty {path}")
    blocks=re.split(r"\n\s*\n",raw)
    out=[]
    for block in blocks:
        lines=block.splitlines()
        if len(lines)<3:
            out.append(block)
            continue
        head=lines[:2]
        text=" ".join(x.strip() for x in lines[2:] if x.strip())
        wrapped=textwrap.wrap(
            text,
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [text]
        out.append("\n".join(head+wrapped))
    Path(path).write_text("\n\n".join(out)+"\n",encoding="utf-8")

def media_duration(path):
    p=subprocess.run([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=nw=1:nk=1",str(path)
    ],capture_output=True,text=True,check=True)
    return float(p.stdout.strip() or 0)

def escape_subtitle_path(path):
    s=str(Path(path).resolve()).replace("\\","/")
    return s.replace(":","\\:").replace("'","\\'")

def render(visual,audio,subtitles,out,duration,font):
    sub=escape_subtitle_path(subtitles)
    force_style=(
        f"FontName={font},FontSize=18,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=120"
    )
    vf=(
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,format=yuv420p,"
        f"subtitles=filename='{sub}':force_style='{force_style}'[v];"
        "[1:a]apad[a]"
    )
    run([
      "ffmpeg","-nostdin","-y","-stream_loop","-1","-i",str(visual),"-i",str(audio),
      "-filter_complex",vf,
      "-map","[v]","-map","[a]","-t",str(duration),
      "-c:v","libx264","-preset","veryfast","-crf","20","-profile:v","high",
      "-c:a","aac","-b:a","160k","-ar","48000","-ac","2","-movflags","+faststart",str(out)
    ])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--visual",required=True)
    ap.add_argument("--en-script",required=True)
    ap.add_argument("--hi-script",required=True)
    ap.add_argument("--out-dir",default="out")
    ap.add_argument("--duration",type=int,default=60)
    ap.add_argument("--min-speech-seconds",type=float,default=0)
    ap.add_argument("--max-speech-seconds",type=float,default=0)
    a=ap.parse_args()
    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    en_text=Path(a.en_script).read_text(encoding="utf-8").strip()
    hi_text=Path(a.hi_script).read_text(encoding="utf-8").strip()
    if not en_text or not hi_text:
        raise SystemExit("English and Hindi scripts must both be non-empty")

    en_audio=out/"voice_en.mp3"
    hi_audio=out/"voice_hi.mp3"
    en_srt=out/"subtitles_en.srt"
    hi_srt=out/"subtitles_hi.srt"

    tts(en_text,"en-US-AriaNeural",en_audio,en_srt)
    tts(hi_text,"hi-IN-SwaraNeural",hi_audio,hi_srt)

    en_duration=media_duration(en_audio)
    hi_duration=media_duration(hi_audio)
    for lang,dur in (("English",en_duration),("Hindi",hi_duration)):
        if a.min_speech_seconds and dur<a.min_speech_seconds:
            raise SystemExit(
                f"{lang} narration too short: {dur:.3f}s < {a.min_speech_seconds}s"
            )
        if a.max_speech_seconds and dur>a.max_speech_seconds:
            raise SystemExit(
                f"{lang} narration too long: {dur:.3f}s > {a.max_speech_seconds}s"
            )
    print(f"EN_SPEECH_SECONDS={en_duration:.3f}")
    print(f"HI_SPEECH_SECONDS={hi_duration:.3f}")

    wrap_srt(en_srt,34)
    wrap_srt(hi_srt,28)

    render(Path(a.visual),en_audio,en_srt,out/"final_en.mp4",a.duration,"Noto Sans")
    render(Path(a.visual),hi_audio,hi_srt,out/"final_hi.mp4",a.duration,"Noto Sans Devanagari")

    print(out/"final_en.mp4")
    print(out/"final_hi.mp4")
    print(en_srt)
    print(hi_srt)

if __name__=="__main__":
    main()
