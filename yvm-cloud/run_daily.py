#!/usr/bin/env python3
import argparse, json, subprocess, sys, time
from pathlib import Path

HERE=Path(__file__).resolve().parent

def run(cmd):
    print("+"," ".join(map(str,cmd)),flush=True)
    subprocess.run([str(x) for x in cmd],check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--workdir",default="out/daily")
    ap.add_argument("--topic")
    ap.add_argument("--scenes",type=int,default=12)
    ap.add_argument("--clip-duration",type=float,default=5)
    ap.add_argument("--final-duration",type=int,default=60)
    a=ap.parse_args()

    wd=Path(a.workdir)
    clips=wd/"clips"
    wd.mkdir(parents=True,exist_ok=True)
    clips.mkdir(parents=True,exist_ok=True)

    plan_path=wd/"plan.json"
    cmd=[sys.executable,HERE/"daily_plan.py","--output",plan_path]
    if a.topic:
        cmd += ["--topic",a.topic]
    run(cmd)
    plan=json.loads(plan_path.read_text())
    prompts=list(plan["scene_prompts"])
    if not prompts:
        raise SystemExit("No scene prompts in plan")

    # Ensure enough prompts without inventing new facts: repeat visual motifs only.
    while len(prompts)<a.scenes:
        prompts.extend(plan["scene_prompts"])
    prompts=prompts[:a.scenes]

    generated=[]
    for i,prompt in enumerate(prompts,1):
        out=clips/f"scene_{i:02d}.mp4"
        if out.exists():
            try:
                run([sys.executable,HERE/"qc_video.py",out,"--min-duration","2","--min-width","400","--min-height","700"])
                generated.append(out)
                continue
            except Exception:
                out.unlink(missing_ok=True)
        run([
            sys.executable,HERE/"failover_generate.py",
            "--prompt",prompt,
            "--output",out,
            "--duration",str(a.clip_duration),
            "--seed",str(1000+i),
        ])
        run([sys.executable,HERE/"qc_video.py",out,"--min-duration","2","--min-width","400","--min-height","700"])
        generated.append(out)
        time.sleep(2)

    visual=wd/"visual_master.mp4"
    run([sys.executable,HERE/"stitch.py","--output",visual,*generated])
    run([sys.executable,HERE/"qc_video.py",visual,"--min-duration","10","--min-width","1000","--min-height","1800"])

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

    result={
        "status":"READY_FOR_UPLOAD",
        "topic":plan["topic"],
        "planner":plan.get("planner"),
        "title_en":plan["title_en"],
        "title_hi":plan["title_hi"],
        "description_en":plan["description_en"],
        "description_hi":plan["description_hi"],
        "tags_en":plan["tags_en"],
        "tags_hi":plan["tags_hi"],
        "final_en":str(render_dir/"final_en.mp4"),
        "final_hi":str(render_dir/"final_hi.mp4"),
        "scene_count":len(generated),
    }
    (wd/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
