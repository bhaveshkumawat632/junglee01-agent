#!/usr/bin/env python3
import argparse, json, os, subprocess, sys, time
from pathlib import Path

HERE=Path(__file__).resolve().parent

def run(cmd, check=True):
    print("+"," ".join(map(str,cmd)),flush=True)
    return subprocess.run([str(x) for x in cmd],check=check)

def credits_from(path):
    if not path.exists():
        return ""
    rows=json.loads(path.read_text())
    lines=[]
    for x in rows:
        if x.get("status")!="ok":
            continue
        title=x.get("title","Wikimedia Commons media")
        artist=x.get("artist") or "Wikimedia Commons contributor"
        lic=x.get("license") or "Wikimedia Commons license"
        page=x.get("page_url") or ""
        lines.append(f"{title} — {artist} — {lic} — {page}")
    if not lines:
        return ""
    return "Visual source credits (Wikimedia Commons):\n" + "\n".join(lines)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--workdir",default="out/daily")
    ap.add_argument("--topic")
    ap.add_argument("--scenes",type=int,default=12)
    ap.add_argument("--clip-duration",type=float,default=5)
    ap.add_argument("--final-duration",type=int,default=60)
    ap.add_argument("--free-video-bonus",type=int,default=2)
    ap.add_argument("--min-ai-motion-scenes",type=int,default=0)
    ap.add_argument("--reuse-plan",action="store_true")
    ap.add_argument("--reuse-kaggle-batch",action="store_true")
    a=ap.parse_args()

    wd=Path(a.workdir)
    clips=wd/"clips"
    assets=wd/"assets"
    wd.mkdir(parents=True,exist_ok=True)
    clips.mkdir(parents=True,exist_ok=True)
    assets.mkdir(parents=True,exist_ok=True)

    plan_path=wd/"plan.json"
    if a.reuse_plan:
        if not plan_path.exists():
            raise SystemExit(f"REUSE_PLAN_MISSING={plan_path}")
        print(f"REUSE_PLAN={plan_path}", flush=True)
    else:
        cmd=[sys.executable,HERE/"daily_plan.py","--output",plan_path]
        if a.topic:
            cmd += ["--topic",a.topic]
        run(cmd)
    run([sys.executable,HERE/"qc_plan.py",plan_path,"--min-scenes",str(min(8,a.scenes))])
    plan=json.loads(plan_path.read_text())
    prompts=list(plan["scene_prompts"])
    if not prompts:
        raise SystemExit("No scene prompts in plan")
    while len(prompts)<a.scenes:
        prompts.extend(plan["scene_prompts"])
    prompts=prompts[:a.scenes]

    # Guaranteed no-card visual baseline:
    # licensed Commons assets first, with a procedural local fallback for missing scenes.
    # The legacy keyless Pollinations image endpoint began returning HTTP 402 and is
    # intentionally disabled rather than silently moving to a paid/authenticated path.
    run([sys.executable,HERE/"commons_assets.py","--plan",plan_path,"--out-dir",assets,"--count",str(a.scenes)])
    run([sys.executable,HERE/"procedural_assets.py","--plan",plan_path,"--out-dir",assets,"--count",str(a.scenes)])
    run([sys.executable,HERE/"images_to_clips.py","--assets",assets,"--out-dir",clips,"--duration",str(a.clip_duration),"--count",str(a.scenes)])

    # Main real-motion lane: submit every scene to Kaggle in one dual-T4 batch.
    # If Kaggle is unavailable, retain the baseline locally and try only legitimate
    # free reserve lanes. Production still fails closed below if too few real
    # AI-motion scenes were produced.
    upgraded=0
    motion_providers=[]
    failed_scene_indices=list(range(1,a.scenes+1))

    if os.getenv("KAGGLE_API_TOKEN") and os.getenv("KAGGLE_USERNAME"):
        batch_ok=False
        try:
            batch_cmd=[
                sys.executable,HERE/"kaggle_batch_generate.py",
                "--plan",plan_path,
                "--out-dir",clips,
                "--count",str(a.scenes),
                "--duration",str(a.clip_duration),
                "--timeout-minutes","80",
            ]
            if a.reuse_kaggle_batch:
                batch_cmd.append("--reuse-existing")
            run(batch_cmd)
            batch_ok=True
        except Exception as e:
            print(f"Kaggle batch retrieval/generation failed; trying reserve lanes: {e}",file=sys.stderr)

        if batch_ok:
            failed_scene_indices=[]
            kaggle_upgraded=0
            for i in range(1,a.scenes+1):
                tmp=clips/f"scene_{i:02d}.ai.mp4"
                dest=clips/f"scene_{i:02d}.mp4"
                try:
                    if not tmp.exists():
                        raise RuntimeError(f"Kaggle batch missing scene {i}")
                    run([
                        sys.executable,HERE/"qc_video.py",tmp,
                        "--min-duration",str(max(2,a.clip_duration-0.2)),
                        "--min-width","300","--min-height","550",
                        "--video-codec","h264"
                    ])
                    # LTX clips can contain intentionally subtle cinematic pans.
                    # Accept either sustained adjacent-frame motion OR meaningful
                    # scene-span motion, but still require high frame uniqueness.
                    run([
                        sys.executable,HERE/"qc_motion.py",tmp,
                        "--min-avg-diff","0.05",
                        "--min-span-diff","0.35",
                        "--min-unique-ratio","0.80",
                        "--motion-mode","any",
                    ])
                    tmp.replace(dest)
                    upgraded+=1
                    kaggle_upgraded+=1
                except Exception as e:
                    print(f"Kaggle scene {i} QC failed; preserving other valid scenes: {e}",file=sys.stderr)
                    tmp.unlink(missing_ok=True)
                    failed_scene_indices.append(i)
            if kaggle_upgraded:
                motion_providers.append("kaggle_t4x2_ltx_batch")

    # Reserve enhancement lanes target only scenes that failed/missed Kaggle QC.
    # This prevents a single weak scene from discarding an otherwise valid batch.
    if failed_scene_indices:
        reserve_candidates=(
            failed_scene_indices
            if os.getenv("AGNES_API_KEY")
            else failed_scene_indices[:max(0,a.free_video_bonus)]
        )
        reserve_upgraded=0
        for i in reserve_candidates:
            dest=clips/f"scene_{i:02d}.mp4"
            tmp=clips/f"scene_{i:02d}.ai.mp4"
            try:
                ref=None
                for ext in (".jpg",".jpeg",".png",".webp"):
                    candidate=assets/f"scene_{i:02d}{ext}"
                    if candidate.exists():
                        ref=candidate
                        break
                cmd=[
                    sys.executable,HERE/"failover_generate.py",
                    "--prompt",prompts[i-1],
                    "--output",tmp,
                    "--duration",str(a.clip_duration),
                    "--seed",str(1000+i),
                ]
                if ref is not None:
                    cmd += ["--reference-image",ref]
                run(cmd)
                run([
                    sys.executable,HERE/"qc_video.py",tmp,
                    "--min-duration","2","--min-width","400","--min-height","700"
                ])
                run([sys.executable,HERE/"qc_motion.py",tmp])
                tmp.replace(dest)
                upgraded+=1
                reserve_upgraded+=1
            except Exception as e:
                print(f"AI upgrade scene {i} skipped: {e}",file=sys.stderr)
                tmp.unlink(missing_ok=True)
            time.sleep(1)
        if reserve_upgraded:
            motion_providers.append("reserve_free_motion")

    if upgraded < a.min_ai_motion_scenes:
        raise SystemExit(
            f"QUALITY GATE FAIL: only {upgraded} real AI-motion scenes; "
            f"required {a.min_ai_motion_scenes}. Refusing weak fallback package."
        )

    ordered=[clips/f"scene_{i:02d}.mp4" for i in range(1,a.scenes+1)]
    for p in ordered:
        if not p.exists():
            raise SystemExit(f"Missing baseline scene: {p}")
    run([sys.executable,HERE/"qc_scene_diversity.py",*ordered])

    visual=wd/"visual_master.mp4"
    run([sys.executable,HERE/"stitch.py","--output",visual,*ordered])
    run([sys.executable,HERE/"qc_video.py",visual,"--min-duration",str(max(10,a.scenes*a.clip_duration-1)),"--min-width","1000","--min-height","1800","--video-codec","h264"])
    run([sys.executable,HERE/"qc_motion.py",visual])

    en=wd/"script_en.txt"
    hi=wd/"script_hi.txt"
    en.write_text(plan["script_en"])
    hi.write_text(plan["script_hi"])

    render_dir=wd/"render"
    run([
        sys.executable,HERE/"render_bilingual.py",
        "--visual",visual,
        "--en-script",en,
        "--hi-script",hi,
        "--out-dir",render_dir,
        "--duration",str(a.final_duration),
        "--min-speech-seconds",str(max(5,a.final_duration-10)),
        "--max-speech-seconds",str(a.final_duration+1.5),
    ])

    for name in ("final_en.mp4","final_hi.mp4"):
        run([
            sys.executable,HERE/"qc_video.py",render_dir/name,
            "--min-duration",str(max(3,a.final_duration-0.5)),
            "--min-width","1000","--min-height","1800","--require-audio",
            "--video-codec","h264","--audio-codec","aac"
        ])

    run([
        sys.executable,HERE/"qc_pair.py",
        "--en-video",render_dir/"final_en.mp4",
        "--hi-video",render_dir/"final_hi.mp4",
        "--en-subtitles",render_dir/"subtitles_en.srt",
        "--hi-subtitles",render_dir/"subtitles_hi.srt",
        "--min-cues","3",
    ])

    credits=credits_from(assets/"attribution.json")
    en_desc=(plan["description_en"].strip()+"\n\n"+credits).strip()
    hi_desc=(plan["description_hi"].strip()+"\n\n"+credits).strip()

    result={
        "status":"READY_FOR_UPLOAD",
        "topic":plan["topic"],
        "planner":plan.get("planner"),
        "title_en":plan["title_en"],
        "title_hi":plan["title_hi"],
        "description_en":en_desc,
        "description_hi":hi_desc,
        "tags_en":plan["tags_en"],
        "tags_hi":plan["tags_hi"],
        "final_en":str(render_dir/"final_en.mp4"),
        "final_hi":str(render_dir/"final_hi.mp4"),
        "scene_count":len(ordered),
        "ai_video_upgrades":upgraded,
        "motion_providers":motion_providers,
        "minimum_ai_motion_scenes_required":a.min_ai_motion_scenes,
        "subtitles_en":str(render_dir/"subtitles_en.srt"),
        "subtitles_hi":str(render_dir/"subtitles_hi.srt"),
        "commons_attribution":str(assets/"attribution.json"),
        "payment_card_used":False,
    }
    (wd/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
