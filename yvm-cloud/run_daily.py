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
    a=ap.parse_args()

    wd=Path(a.workdir)
    clips=wd/"clips"
    assets=wd/"assets"
    wd.mkdir(parents=True,exist_ok=True)
    clips.mkdir(parents=True,exist_ok=True)
    assets.mkdir(parents=True,exist_ok=True)

    plan_path=wd/"plan.json"
    cmd=[sys.executable,HERE/"daily_plan.py","--output",plan_path]
    if a.topic:
        cmd += ["--topic",a.topic]
    run(cmd)
    plan=json.loads(plan_path.read_text())
    prompts=list(plan["scene_prompts"])
    if not prompts:
        raise SystemExit("No scene prompts in plan")
    while len(prompts)<a.scenes:
        prompts.extend(plan["scene_prompts"])
    prompts=prompts[:a.scenes]

    # Guaranteed no-card visual baseline:
    # keyless AI images first, then freely licensed Commons only for missing scenes.
    try:
        run([sys.executable,HERE/"pollinations_images.py","--plan",plan_path,"--out-dir",assets,"--count",str(a.scenes)])
    except Exception as e:
        print(f"keyless AI image lane degraded: {e}",file=sys.stderr)
    run([sys.executable,HERE/"commons_assets.py","--plan",plan_path,"--out-dir",assets,"--count",str(a.scenes)])
    run([sys.executable,HERE/"images_to_clips.py","--assets",assets,"--out-dir",clips,"--duration",str(a.clip_duration),"--count",str(a.scenes)])

    # Enhancement lane. With Agnes configured, upgrade every scene.
    # Without Agnes, use only a small legitimate ZeroGPU bonus and keep the Commons baseline if quota is unavailable.
    upgrade_count=a.scenes if os.getenv("AGNES_API_KEY") else min(a.free_video_bonus,a.scenes)
    upgraded=0
    for i in range(1,upgrade_count+1):
        dest=clips/f"scene_{i:02d}.mp4"
        tmp=clips/f"scene_{i:02d}.ai.mp4"
        try:
            run([
                sys.executable,HERE/"failover_generate.py",
                "--prompt",prompts[i-1],
                "--output",tmp,
                "--duration",str(a.clip_duration),
                "--seed",str(1000+i),
            ])
            run([sys.executable,HERE/"qc_video.py",tmp,"--min-duration","2","--min-width","400","--min-height","700"])
            tmp.replace(dest)
            upgraded+=1
        except Exception as e:
            print(f"AI upgrade scene {i} skipped: {e}",file=sys.stderr)
            tmp.unlink(missing_ok=True)
        time.sleep(1)

    ordered=[clips/f"scene_{i:02d}.mp4" for i in range(1,a.scenes+1)]
    for p in ordered:
        if not p.exists():
            raise SystemExit(f"Missing baseline scene: {p}")

    visual=wd/"visual_master.mp4"
    run([sys.executable,HERE/"stitch.py","--output",visual,*ordered])
    run([sys.executable,HERE/"qc_video.py",visual,"--min-duration",str(max(10,a.scenes*a.clip_duration-1)),"--min-width","1000","--min-height","1800"])

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
    ])

    for name in ("final_en.mp4","final_hi.mp4"):
        run([
            sys.executable,HERE/"qc_video.py",render_dir/name,
            "--min-duration",str(max(3,a.final_duration-0.5)),
            "--min-width","1000","--min-height","1800","--require-audio"
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
        "commons_attribution":str(assets/"attribution.json"),
        "payment_card_used":False,
    }
    (wd/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
