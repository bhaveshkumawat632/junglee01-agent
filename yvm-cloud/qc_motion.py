#!/usr/bin/env python3
"""Lightweight motion QC for YVM video clips.

Uses ffmpeg to decode a small grayscale sample stream. This detects static or
near-static loops without requiring OpenCV, CUDA, or a heavy ML dependency.
"""
import argparse
import hashlib
import json
import subprocess


def probe(path):
    p = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-show_entries", "format=duration",
            "-of", "json", path,
        ],
        capture_output=True, text=True, check=True,
    )
    return json.loads(p.stdout)


def sample_frames(path, fps, size):
    cmd = [
        "ffmpeg", "-nostdin", "-v", "error", "-i", path,
        "-vf", f"fps={fps},scale={size}:{size}:flags=area,format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    p = subprocess.run(cmd, capture_output=True, check=True)
    frame_bytes = size * size
    raw = p.stdout
    if len(raw) < frame_bytes:
        return []
    return [
        raw[i:i + frame_bytes]
        for i in range(0, len(raw) - frame_bytes + 1, frame_bytes)
    ]


def mean_abs_diff(a, b):
    if len(a) != len(b) or not a:
        return 0.0
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--sample-fps", type=float, default=2.0)
    ap.add_argument("--sample-size", type=int, default=64)
    ap.add_argument("--min-avg-diff", type=float, default=0.50)
    ap.add_argument("--min-span-diff", type=float, default=1.50)
    ap.add_argument("--min-unique-ratio", type=float, default=0.50)
    ap.add_argument("--motion-mode", choices=("all", "any"), default="all",
                    help="all: avg and span thresholds must pass; any: either motion threshold may pass. Unique-frame ratio is always required.")
    a = ap.parse_args()

    meta = probe(a.file)
    frames = sample_frames(a.file, a.sample_fps, a.sample_size)
    if len(frames) < 2:
        raise SystemExit("MOTION QC FAIL: fewer than 2 sampled frames")

    adjacent = [mean_abs_diff(x, y) for x, y in zip(frames, frames[1:])]
    avg_diff = sum(adjacent) / len(adjacent)
    span_diff = mean_abs_diff(frames[0], frames[-1])
    unique = len({hashlib.sha256(x).digest() for x in frames})
    unique_ratio = unique / len(frames)

    result = {
        "status": "PASS",
        "samples": len(frames),
        "unique_samples": unique,
        "unique_ratio": round(unique_ratio, 4),
        "avg_adjacent_pixel_diff": round(avg_diff, 4),
        "first_last_pixel_diff": round(span_diff, 4),
        "duration": float((meta.get("format") or {}).get("duration") or 0),
    }

    failures = []
    avg_ok = avg_diff >= a.min_avg_diff
    span_ok = span_diff >= a.min_span_diff
    if a.motion_mode == "all":
        if not avg_ok:
            failures.append(f"avg motion {avg_diff:.4f} < {a.min_avg_diff}")
        if not span_ok:
            failures.append(f"span motion {span_diff:.4f} < {a.min_span_diff}")
    elif not (avg_ok or span_ok):
        failures.append(
            "motion below both thresholds "
            f"(avg {avg_diff:.4f} < {a.min_avg_diff}; "
            f"span {span_diff:.4f} < {a.min_span_diff})"
        )
    if unique_ratio < a.min_unique_ratio:
        failures.append(f"unique ratio {unique_ratio:.4f} < {a.min_unique_ratio}")
    if failures:
        result["status"] = "FAIL"
        print(json.dumps(result, indent=2))
        raise SystemExit("MOTION QC FAIL: " + "; ".join(failures))

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
