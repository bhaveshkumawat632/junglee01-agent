#!/usr/bin/env python3
import argparse
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector

def sh(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def ffprobe(path):
    p = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path)
    ], capture_output=True, text=True, check=True)
    return float(p.stdout.strip() or 0)

def black_freeze(path):
    _, _, err = sh([
        "ffmpeg", "-hide_banner", "-nostdin", "-i", str(path),
        "-vf", "blackdetect=d=0.35:pix_th=0.10,freezedetect=n=-50dB:d=0.7",
        "-an", "-f", "null", "-"
    ])
    black = len(re.findall(r"black_start:", err))
    freeze = len(re.findall(r"freeze_start:", err))
    return black, freeze

def detect_scenes(path, threshold=24.0):
    video = open_video(str(path))
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=threshold, min_scene_len=12))
    sm.detect_scenes(video=video)
    scenes = sm.get_scene_list(start_in_scene=True)
    rows = []
    for a, b in scenes:
        rows.append((a.get_seconds(), b.get_seconds(), b.get_seconds() - a.get_seconds()))
    return rows

def sample_frames(path, count, outdir):
    dur = ffprobe(path)
    frames = []
    for i in range(count):
        t = (i + 0.5) * dur / count
        out = outdir / f"frame_{i+1:02d}.jpg"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
            "-i", str(path), "-frames:v", "1", "-q:v", "2", str(out)
        ], check=True)
        frames.append(out)
    return frames

def dhash(path):
    im = Image.open(path).convert("L").resize((17, 16))
    a = np.asarray(im, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return bits

def hamming(a, b):
    return float(np.mean(a != b))

def frame_uniqueness(frames):
    hs = [dhash(x) for x in frames]
    if len(hs) < 2:
        return 0.0, 0.0
    adj = [hamming(a, b) for a, b in zip(hs, hs[1:])]
    pair = []
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            pair.append(hamming(hs[i], hs[j]))
    return float(np.mean(adj)), float(np.mean(pair))

def clip_scores(frames, prompts, topic):
    import torch, open_clip
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k", device="cpu"
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    good_text = (
        f"high quality photorealistic documentary footage about {topic}, "
        "natural anatomy, coherent objects, cinematic composition, realistic lighting"
    )
    bad_text = (
        "low quality AI generated video frame, distorted anatomy, mannequin face, "
        "nonsense text, warped objects, blurry incoherent composition, surreal artifacts"
    )
    sem = []
    good_margin = []
    with torch.no_grad():
        for i, f in enumerate(frames):
            img = preprocess(Image.open(f).convert("RGB")).unsqueeze(0)
            texts = [prompts[min(i, len(prompts) - 1)], good_text, bad_text]
            tok = tokenizer(texts)
            imf = model.encode_image(img)
            txf = model.encode_text(tok)
            imf = imf / imf.norm(dim=-1, keepdim=True)
            txf = txf / txf.norm(dim=-1, keepdim=True)
            vals = (imf @ txf.T).squeeze(0).cpu().numpy().astype(float)
            sem.append(vals[0])
            good_margin.append(vals[1] - vals[2])
    return sem, good_margin

def compute_v2_creative_score(plan, clip_sem_mean, clip_margin_mean, adj_diff, scenes_count, black, freeze, dur):
    script_en = plan.get("script_en", "")
    script_hi = plan.get("script_hi", "")
    topic = plan.get("topic", "")

    hook_score = 20
    first_sentence = script_en.split(".")[0] if "." in script_en else script_en[:80]
    bad_hooks = ("hello", "today we", "in this video", "here is the story", "here is what", "hey guys")
    if any(first_sentence.lower().strip().startswith(b) for b in bad_hooks):
        hook_score -= 15
    if len(first_sentence.split()) > 25:
        hook_score -= 5
    if len(first_sentence.split()) < 4:
        hook_score -= 8
    hook_score = max(0, min(20, hook_score))

    script_score = 20
    en_words = len(script_en.split())
    if en_words < 110 or en_words > 170:
        script_score -= 6
    generic_markers = [
        "the practical takeaway is simple",
        "first online reaction is often louder",
        "focus on what is actually known",
        "watch for the next measurable signal"
    ]
    for gm in generic_markers:
        if gm in script_en.lower():
            script_score -= 8
    script_score = max(0, min(20, script_score))

    sem_norm = max(0.0, min(1.0, (clip_sem_mean - 0.18) / 0.14))
    vis_rel_score = round(sem_norm * 15, 1)

    margin_norm = max(0.0, min(1.0, (clip_margin_mean + 0.01) / 0.12))
    vis_qual_score = round(margin_norm * 15, 1)
    if black > 0 or freeze > 0:
        vis_qual_score = max(0.0, vis_qual_score - 5.0)

    edit_score = 10
    if scenes_count < 8:
        edit_score -= 5
    if adj_diff < 0.06:
        edit_score -= 3
    edit_score = max(0, min(10, edit_score))

    narration_score = 10
    if dur < 57.0 or dur > 61.0:
        narration_score -= 4
    narration_score = max(0, min(10, narration_score))

    caption_score = 5
    audio_score = 5

    total = round(
        hook_score + script_score + vis_rel_score + vis_qual_score +
        edit_score + narration_score + caption_score + audio_score, 1
    )

    scores = {
        "HOOK_SCORE": hook_score,
        "SCRIPT_SCORE": script_score,
        "VISUAL_RELEVANCE_SCORE": vis_rel_score,
        "VISUAL_QUALITY_SCORE": vis_qual_score,
        "EDITING_SCORE": edit_score,
        "NARRATION_SCORE": narration_score,
        "CAPTION_SCORE": caption_score,
        "AUDIO_SCORE": audio_score,
        "TOTAL_CREATIVE_SCORE": total,
    }
    return scores

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--expected-scenes", type=int, default=12)
    ap.add_argument("--min-detected-scenes", type=int, default=8)
    ap.add_argument("--max-long-scene", type=float, default=12.0)
    ap.add_argument("--min-adj-hash-diff", type=float, default=0.06)
    ap.add_argument("--min-pair-hash-diff", type=float, default=0.10)
    ap.add_argument("--min-clip-score", type=float, default=0.18)
    ap.add_argument("--min-good-margin", type=float, default=-0.01)
    ap.add_argument("--min-total-score", type=float, default=85.0)
    a = ap.parse_args()

    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    prompts = list(plan.get("scene_prompts") or [])
    topic = str(plan.get("topic") or "").strip()
    if len(prompts) < a.expected_scenes or not topic:
        raise SystemExit("CREATIVE QC FAIL: incomplete topic/scene prompts")

    dur = ffprobe(a.video)
    black, freeze = black_freeze(a.video)
    scenes = detect_scenes(a.video)
    long_scenes = [x for x in scenes if x[2] > a.max_long_scene]

    with tempfile.TemporaryDirectory() as td:
        frames = sample_frames(a.video, a.expected_scenes, Path(td))
        adj_diff, pair_diff = frame_uniqueness(frames)
        sem, margin = clip_scores(frames, prompts[:a.expected_scenes], topic)

    sem_mean = float(np.mean(sem))
    margin_mean = float(np.mean(margin))

    score_card = compute_v2_creative_score(
        plan, sem_mean, margin_mean, adj_diff, len(scenes), black, freeze, dur
    )

    report = {
        "status": "PASS",
        "creative_scores": score_card,
        "black_segments": black,
        "freeze_segments": freeze,
        "detected_scenes": len(scenes),
        "scene_durations": [round(x[2], 3) for x in scenes],
        "long_scene_count": len(long_scenes),
        "adjacent_frame_hash_diff": round(adj_diff, 4),
        "pairwise_frame_hash_diff": round(pair_diff, 4),
        "clip_scene_scores": [round(x, 4) for x in sem],
        "clip_scene_score_mean": round(sem_mean, 4),
        "clip_scene_score_min": round(float(np.min(sem)), 4),
        "good_vs_bad_margins": [round(x, 4) for x in margin],
        "good_vs_bad_margin_mean": round(margin_mean, 4),
        "good_vs_bad_margin_min": round(float(np.min(margin)), 4),
    }

    failures = []
    if black:
        failures.append(f"black segments={black}")
    if freeze:
        failures.append(f"freeze segments={freeze}")
    if len(scenes) < a.min_detected_scenes:
        failures.append(f"scene cadence too low: {len(scenes)} < {a.min_detected_scenes}")
    if long_scenes:
        failures.append(f"{len(long_scenes)} scene(s) longer than {a.max_long_scene}s")
    if adj_diff < a.min_adj_hash_diff:
        failures.append(f"adjacent visual diversity {adj_diff:.4f} < {a.min_adj_hash_diff}")
    if pair_diff < a.min_pair_hash_diff:
        failures.append(f"overall visual diversity {pair_diff:.4f} < {a.min_pair_hash_diff}")
    if min(sem) < a.min_clip_score:
        failures.append(f"scene relevance min {min(sem):.4f} < {a.min_clip_score}")
    if min(margin) < a.min_good_margin:
        failures.append(f"AI-artifact quality margin min {min(margin):.4f} < {a.min_good_margin}")
    if score_card["TOTAL_CREATIVE_SCORE"] < a.min_total_score:
        failures.append(f"Total creative score {score_card['TOTAL_CREATIVE_SCORE']} < {a.min_total_score}")

    if failures:
        report["status"] = "FAIL"
        report["failures"] = failures
        print(json.dumps(report, indent=2))
        raise SystemExit("CREATIVE QC FAIL: " + "; ".join(failures))

    print(json.dumps(report, indent=2))
    print(f"YVM_V2_CREATIVE_SCORE={score_card['TOTAL_CREATIVE_SCORE']}")
    print("YVM_CREATIVE_QC=PASS")

if __name__ == "__main__":
    main()
