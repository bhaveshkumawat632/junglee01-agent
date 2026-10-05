#!/usr/bin/env python3
"""Reject exact or near-duplicate scene clips using lightweight frame fingerprints."""
import argparse
import hashlib
import itertools
import json
import subprocess

def duration(path):
    p=subprocess.run([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=nw=1:nk=1",path
    ],capture_output=True,text=True,check=True)
    return float(p.stdout.strip() or 0)

def mid_frame(path,size):
    d=duration(path)
    if d<=0:
        raise RuntimeError(f"invalid duration: {path}")
    p=subprocess.run([
        "ffmpeg","-nostdin","-v","error","-ss",str(d/2),"-i",path,
        "-frames:v","1","-vf",f"scale={size}:{size}:flags=area,format=gray",
        "-f","rawvideo","-pix_fmt","gray","-"
    ],capture_output=True,check=True)
    expected=size*size
    if len(p.stdout)<expected:
        raise RuntimeError(f"could not sample frame: {path}")
    return p.stdout[:expected]

def mean_abs_diff(a,b):
    return sum(abs(x-y) for x,y in zip(a,b))/len(a)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("clips",nargs="+")
    ap.add_argument("--sample-size",type=int,default=64)
    ap.add_argument("--min-pair-diff",type=float,default=1.0)
    a=ap.parse_args()
    if len(a.clips)<2:
        raise SystemExit("SCENE DIVERSITY FAIL: need at least two clips")

    frames={p:mid_frame(p,a.sample_size) for p in a.clips}
    exact=len({hashlib.sha256(v).digest() for v in frames.values()})
    pairs=[]
    for x,y in itertools.combinations(a.clips,2):
        pairs.append({"a":x,"b":y,"diff":round(mean_abs_diff(frames[x],frames[y]),4)})
    closest=min(pairs,key=lambda x:x["diff"])
    result={
        "status":"PASS",
        "scene_count":len(a.clips),
        "unique_mid_frames":exact,
        "closest_pair":closest,
        "min_pair_diff_required":a.min_pair_diff,
    }
    failures=[]
    if exact!=len(a.clips):
        failures.append("exact duplicate sampled frames detected")
    if closest["diff"]<a.min_pair_diff:
        failures.append(
            f"closest scene difference {closest['diff']} < {a.min_pair_diff}"
        )
    if failures:
        result["status"]="FAIL"
        print(json.dumps(result,indent=2))
        raise SystemExit("SCENE DIVERSITY FAIL: "+"; ".join(failures))
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
