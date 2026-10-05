#!/usr/bin/env python3
import argparse, subprocess, tempfile
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    ap.add_argument("clips",nargs="+")
    a=ap.parse_args()
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",suffix=".txt",delete=False) as f:
        for c in a.clips:
            p=Path(c).resolve()
            f.write("file '"+str(p).replace("'","'\\''")+"'"+"\n")
        listfile=f.name
    subprocess.run([
      "ffmpeg","-nostdin","-y","-f","concat","-safe","0","-i",listfile,
      "-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p",
      "-an","-c:v","libx264","-preset","veryfast","-crf","20","-movflags","+faststart",str(out)
    ],check=True)
    print(out)
if __name__=="__main__":
    main()
