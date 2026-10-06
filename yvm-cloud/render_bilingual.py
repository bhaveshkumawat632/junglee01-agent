#!/usr/bin/env python3
import argparse
import re
import subprocess
import textwrap
from pathlib import Path

def run(cmd):
    print("+"," ".join(map(str,cmd)),flush=True)
    subprocess.run([str(x) for x in cmd],check=True)

def tts(text, voice, audio_out, subtitle_out, rate_pct=0):
    cmd=[
        "edge-tts",
        "--voice",voice,
        "--text",text,
    ]
    if rate_pct:
        cmd.append(f"--rate={int(round(rate_pct)):+d}%")
    cmd += [
        "--write-media",str(audio_out),
        "--write-subtitles",str(subtitle_out),
    ]
    run(cmd)

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


def fitted_tts(text, voice, audio_out, subtitle_out, min_seconds=0, max_seconds=0):
    """Generate TTS and adapt speaking rate until it fits the requested window.

    Regenerating through edge-tts keeps subtitle timings synchronized with audio,
    unlike post-processing the MP3 with atempo.
    """
    rate_pct=0.0
    attempts=4
    for attempt in range(1,attempts+1):
        tts(text,voice,audio_out,subtitle_out,rate_pct=rate_pct)
        dur=media_duration(audio_out)
        too_short=bool(min_seconds and dur < min_seconds)
        too_long=bool(max_seconds and dur > max_seconds)
        if not too_short and not too_long:
            return dur,rate_pct

        if too_long:
            target=max_seconds-1.5 if max_seconds>2 else max_seconds
            if min_seconds:
                target=max(target,min_seconds+1.0)
        else:
            target=min_seconds+1.5
            if max_seconds:
                target=min(target,max_seconds-1.0)

        target=max(1.0,target)
        current_speed=max(0.1,1.0+rate_pct/100.0)
        desired_speed=current_speed*(dur/target)
        next_rate=(desired_speed-1.0)*100.0
        next_rate=max(-40.0,min(60.0,next_rate))
        if abs(next_rate-rate_pct) < 1.0:
            next_rate=rate_pct+(2.0 if too_long else -2.0)
        rate_pct=next_rate
        print(
            f"TTS_FIT retry={attempt} duration={dur:.3f}s "
            f"target={target:.3f}s next_rate={rate_pct:+.1f}%"
        )

    dur=media_duration(audio_out)
    if min_seconds and dur < min_seconds:
        raise SystemExit(f"Narration too short after rate fitting: {dur:.3f}s < {min_seconds}s")
    if max_seconds and dur > max_seconds:
        raise SystemExit(f"Narration too long after rate fitting: {dur:.3f}s > {max_seconds}s")
    return dur,rate_pct

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

    en_duration,en_rate=fitted_tts(
        en_text,"en-US-AriaNeural",en_audio,en_srt,
        a.min_speech_seconds,a.max_speech_seconds
    )
    hi_duration,hi_rate=fitted_tts(
        hi_text,"hi-IN-SwaraNeural",hi_audio,hi_srt,
        a.min_speech_seconds,a.max_speech_seconds
    )
    print(f"EN_SPEECH_SECONDS={en_duration:.3f}")
    print(f"HI_SPEECH_SECONDS={hi_duration:.3f}")
    print(f"EN_TTS_RATE={en_rate:+.1f}%")
    print(f"HI_TTS_RATE={hi_rate:+.1f}%")

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
