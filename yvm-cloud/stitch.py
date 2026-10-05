#!/usr/bin/env python3
import argparse, subprocess, tempfile
from pathlib import Path

def run(cmd):
    print("+"," ".join(map(str,cmd)),flush=True)
    subprocess.run([str(x) for x in cmd],check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    ap.add_argument("clips",nargs="+")
    a=ap.parse_args()
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="yvm-norm-") as td:
        td=Path(td)
        norm=[]
        for i,clip in enumerate(a.clips,1):
            dest=td/f"{i:03d}.mp4"
            run([
              "ffmpeg","-nostdin","-y","-i",clip,
              "-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p",
              "-an","-c:v","libx264","-preset","veryfast","-crf","20",
              "-profile:v","high","-movflags","+faststart",dest
            ])
            norm.append(dest)

        listfile=td/"concat.txt"
        with listfile.open("w") as fh:
            for p in norm:
                fh.write("file '"+str(p).replace("'","'\\''")+"'\n")

        run([
          "ffmpeg","-nostdin","-y","-f","concat","-safe","0","-i",listfile,
          "-c:v","copy","-an","-movflags","+faststart",out
        ])
    print(out)

if __name__=="__main__":
    main()
