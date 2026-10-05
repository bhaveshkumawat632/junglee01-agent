#!/usr/bin/env python3
import argparse, subprocess
from pathlib import Path

def run(cmd):
    print("+"," ".join(map(str,cmd)))
    subprocess.run(cmd,check=True)

def tts(text, voice, out):
    run(["edge-tts","--voice",voice,"--text",text,"--write-media",str(out)])

def render(visual,audio,out,duration):
    run([
      "ffmpeg","-nostdin","-y","-stream_loop","-1","-i",str(visual),"-i",str(audio),
      "-filter_complex",
      "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p[v];[1:a]apad[a]",
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
    a=ap.parse_args()
    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    en_text=Path(a.en_script).read_text().strip()
    hi_text=Path(a.hi_script).read_text().strip()
    tts(en_text,"en-US-AriaNeural",out/"voice_en.mp3")
    tts(hi_text,"hi-IN-SwaraNeural",out/"voice_hi.mp3")
    render(Path(a.visual),out/"voice_en.mp3",out/"final_en.mp4",a.duration)
    render(Path(a.visual),out/"voice_hi.mp3",out/"final_hi.mp4",a.duration)
    print(out/"final_en.mp4")
    print(out/"final_hi.mp4")
if __name__=="__main__":
    main()
