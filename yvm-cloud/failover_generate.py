#!/usr/bin/env python3
import argparse, os, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent

def run(cmd):
    print("+"," ".join(map(str,cmd)),flush=True)
    subprocess.run(cmd,check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prompt",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--duration",type=float,default=5)
    ap.add_argument("--seed",type=int,default=-1)
    a=ap.parse_args()
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)

    errors=[]
    if os.getenv("AGNES_API_KEY"):
        try:
            run([sys.executable,str(HERE/"agnes_video.py"),"--prompt",a.prompt,"--output",str(out),"--duration",str(int(a.duration)),"--width","768","--height","1152"])
            print("PROVIDER=agnes")
            return
        except Exception as e:
            errors.append(f"agnes:{e}")

    try:
        run([sys.executable,str(HERE/"ltx_zerogpu.py"),"--prompt",a.prompt,"--output",str(out),"--duration",str(a.duration),"--seed",str(a.seed)])
        print("PROVIDER=hf_ltx_zerogpu")
        return
    except Exception as e:
        errors.append(f"hf_ltx_zerogpu:{e}")

    try:
        run([sys.executable,str(HERE/"deeprat_ltx.py"),"--prompt",a.prompt,"--output",str(out),"--duration",str(min(a.duration,3.0)),"--seed",str(a.seed if a.seed >= 0 else 42)])
        print("PROVIDER=hf_deeprat_zerogpu")
        return
    except Exception as e:
        errors.append(f"hf_deeprat_zerogpu:{e}")

    raise SystemExit("All configured no-card providers failed: "+" | ".join(errors))

if __name__=="__main__":
    main()
