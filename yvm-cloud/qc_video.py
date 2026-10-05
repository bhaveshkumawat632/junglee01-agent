#!/usr/bin/env python3
import argparse, json, subprocess, sys

def probe(path):
    p=subprocess.run([
      "ffprobe","-v","error","-print_format","json",
      "-show_streams","-show_format",path
    ],capture_output=True,text=True,check=True)
    return json.loads(p.stdout)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--min-duration",type=float,default=3.0)
    ap.add_argument("--min-width",type=int,default=360)
    ap.add_argument("--min-height",type=int,default=640)
    ap.add_argument("--require-audio",action="store_true")
    a=ap.parse_args()
    d=probe(a.file)
    fmt=d.get("format",{})
    streams=d.get("streams",[])
    dur=float(fmt.get("duration") or 0)
    vs=[s for s in streams if s.get("codec_type")=="video"]
    aud=[s for s in streams if s.get("codec_type")=="audio"]
    if not vs: raise SystemExit("QC FAIL: no video stream")
    v=vs[0]
    w=int(v.get("width") or 0); h=int(v.get("height") or 0)
    if dur<a.min_duration: raise SystemExit(f"QC FAIL: duration {dur}")
    if w<a.min_width or h<a.min_height: raise SystemExit(f"QC FAIL: resolution {w}x{h}")
    if a.require_audio and not aud: raise SystemExit("QC FAIL: no audio")
    print(json.dumps({"status":"PASS","duration":dur,"width":w,"height":h,"video_codec":v.get("codec_name"),"audio_codec":aud[0].get("codec_name") if aud else None},indent=2))
if __name__=="__main__":
    main()
