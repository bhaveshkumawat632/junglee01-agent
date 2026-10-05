#!/usr/bin/env python3
import argparse, os, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent

def run(cmd):
    print("+"," ".join(map(str,cmd)),flush=True)
    subprocess.run([str(x) for x in cmd],check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prompt",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--duration",type=float,default=5)
    ap.add_argument("--seed",type=int,default=-1)
    ap.add_argument("--reference-image")
    a=ap.parse_args()
    out=Path(a.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    seed=a.seed if a.seed >= 0 else 42
    errors=[]

    # Optional Vidu lane. vidu_video.py explicitly forces claw_pass and
    # refuses to fall back to normal credits.
    if os.getenv("VIDU_TOKEN"):
        try:
            cmd=[sys.executable,HERE/"vidu_video.py",
                 "--prompt",a.prompt,"--output",out,
                 "--duration",str(max(1,min(16,int(round(a.duration)))))]
            run(cmd)
            print("PROVIDER=vidu_claw_pass")
            return
        except Exception as e:
            errors.append(f"vidu:{e}")
            out.unlink(missing_ok=True)

    # Optional free Agnes lane when the user has configured a no-card key.
    if os.getenv("AGNES_API_KEY"):
        try:
            cmd=[sys.executable,HERE/"agnes_video.py",
                 "--prompt",a.prompt,"--output",out,
                 "--duration",str(max(1,int(round(a.duration)))),
                 "--width","768","--height","1152"]
            run(cmd)
            print("PROVIDER=agnes")
            return
        except Exception as e:
            errors.append(f"agnes:{e}")
            out.unlink(missing_ok=True)

    # Primary keyless motion lane proven live on GitHub-hosted runners.
    try:
        run([sys.executable,HERE/"wan_zerogpu.py",
             "--prompt",a.prompt,"--output",out,
             "--duration",str(a.duration),"--steps","8","--seed",str(seed)])
        print("PROVIDER=hf_wan21_base")
        return
    except Exception as e:
        errors.append(f"hf_wan21_base:{e}")
        out.unlink(missing_ok=True)

    # Image-to-video rescue lane when a reference frame is available.
    if a.reference_image:
        try:
            run([sys.executable,HERE/"wan22_i2v.py",
                 "--image",a.reference_image,
                 "--prompt",a.prompt,"--output",out,
                 "--duration",str(min(a.duration,3.5)),"--steps","4","--seed",str(seed)])
            print("PROVIDER=hf_wan22_i2v")
            return
        except Exception as e:
            errors.append(f"hf_wan22_i2v:{e}")
            out.unlink(missing_ok=True)

    # LTX works keylessly but has a small anonymous daily ZeroGPU quota.
    try:
        run([sys.executable,HERE/"ltx_zerogpu.py",
             "--prompt",a.prompt,"--output",out,
             "--duration",str(a.duration),"--seed",str(seed),"--attempts","1"])
        print("PROVIDER=hf_ltx_zerogpu")
        return
    except Exception as e:
        errors.append(f"hf_ltx_zerogpu:{e}")
        out.unlink(missing_ok=True)

    # Last public reserve.
    try:
        run([sys.executable,HERE/"deeprat_ltx.py",
             "--prompt",a.prompt,"--output",out,
             "--duration",str(min(a.duration,3.0)),"--seed",str(seed)])
        print("PROVIDER=hf_deeprat_zerogpu")
        return
    except Exception as e:
        errors.append(f"hf_deeprat_zerogpu:{e}")
        out.unlink(missing_ok=True)

    raise SystemExit("All configured no-card motion providers failed: "+" | ".join(errors))

if __name__=="__main__":
    main()
