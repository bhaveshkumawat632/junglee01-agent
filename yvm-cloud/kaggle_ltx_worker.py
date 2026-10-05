#!/usr/bin/env python3
"""Kaggle T4x2 benchmark worker for LTX-Video 2B distilled.

Runs entirely inside a Kaggle GPU notebook/script. It does not use paid APIs.
The script creates one vertical motion clip and writes machine-readable metrics
next to the output so GitHub Actions can calculate practical capacity.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

WORK=Path("/kaggle/working")
SRC=WORK/"LTX-Video"
OUTDIR=WORK/"ltx_out"
RESULT=WORK/"yvm_kaggle_result.json"
FINAL=WORK/"yvm_kaggle_clip.mp4"

PROMPT=os.getenv(
    "YVM_PROMPT",
    "A cinematic documentary shot on a 1990s Wall Street trading floor. "
    "Adult professional traders move quickly between desks filled with CRT monitors, "
    "phones and printed market sheets. The camera slowly pushes forward through the "
    "busy room while people gesture and exchange information. Authentic period office "
    "lighting, realistic human motion, financial newsroom atmosphere, no logos, "
    "no readable text, no watermark, vertical composition."
)

def run(cmd, cwd=None):
    print("+"," ".join(map(str,cmd)),flush=True)
    subprocess.run([str(x) for x in cmd],cwd=cwd,check=True)

def main():
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    started=time.time()
    gpu=subprocess.run(["nvidia-smi","--query-gpu=name,memory.total","--format=csv,noheader"],
                       text=True,capture_output=True)
    if gpu.returncode:
        raise SystemExit("KAGGLE_GPU_NOT_AVAILABLE")
    print("GPUS=\n"+gpu.stdout,flush=True)
    gpu_lines=[line.strip() for line in gpu.stdout.splitlines() if line.strip()]

    if not SRC.exists():
        run(["git","clone","--depth","1","https://github.com/Lightricks/LTX-Video.git",SRC])

    patch_script = """
import pathlib
f1 = pathlib.Path('LTX-Video/ltx_video/inference.py')
c1 = f1.read_text()
c1 = c1.replace('text_encoder = text_encoder.to(device)', 'import torch\\n    text_encoder = text_encoder.to("cuda:1" if torch.cuda.device_count() > 1 else device)')
f1.write_text(c1)

f2 = pathlib.Path('LTX-Video/ltx_video/pipelines/pipeline_ltx_video.py')
c2 = f2.read_text()
c2 = c2.replace('prompt_attention_mask = prompt_attention_mask.to(device)', 'prompt_attention_mask = prompt_attention_mask.to(self._execution_device)')
c2 = c2.replace('prompt_embeds = prompt_embeds[0]', 'prompt_embeds = prompt_embeds[0].to(self._execution_device)')
c2 = c2.replace('negative_prompt_embeds = negative_prompt_embeds[0]', 'negative_prompt_embeds = negative_prompt_embeds[0].to(self._execution_device)')
c2 = c2.replace('self.text_encoder = self.text_encoder.to(self._execution_device)', 'pass')
f2.write_text(c2)
"""
    Path("patch.py").write_text(patch_script)
    run([sys.executable, "patch.py"])

    # Official inference dependencies.
    run([sys.executable,"-m","pip","install","-q","-e",".[inference]","accelerate"],cwd=SRC)

    # Upstream LTX creates the pipeline by moving transformer + VAE + the large
    # PixArt T5 encoder onto CUDA at the same time. On a 15 GiB T4 this can OOM
    # before inference starts, even when --offload_to_cpu is requested.
    # Patch the freshly-cloned upstream inference loader so components stay on
    # CPU during construction and Diffusers moves one model at a time.
    inference_py=SRC/"ltx_video/inference.py"
    source=inference_py.read_text()
    old_encoder='''    text_encoder = T5EncoderModel.from_pretrained(
        text_encoder_model_name_or_path, subfolder="text_encoder"
    )'''
    new_encoder='''    text_encoder = T5EncoderModel.from_pretrained(
        text_encoder_model_name_or_path,
        subfolder="text_encoder",
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
    )'''
    old_moves='''    transformer = transformer.to(device)
    vae = vae.to(device)
    text_encoder = text_encoder.to(device)
'''
    new_moves='''    # YVM T4 patch: keep large modules on CPU until the offload hooks need them.
'''
    old_pipeline='''    pipeline = LTXVideoPipeline(**submodel_dict)
    pipeline = pipeline.to(device)
    return pipeline'''
    new_pipeline='''    pipeline = LTXVideoPipeline(**submodel_dict)
    if str(device).startswith("cuda"):
        pipeline.enable_model_cpu_offload()
    else:
        pipeline = pipeline.to(device)
    return pipeline'''
    for old,new,label in [
        (old_encoder,new_encoder,"text_encoder_bf16"),
        (old_moves,new_moves,"initial_cuda_moves"),
        (old_pipeline,new_pipeline,"pipeline_cpu_offload"),
    ]:
        if old not in source:
            raise RuntimeError(f"LTX_PATCH_TARGET_MISSING={label}")
        source=source.replace(old,new,1)
    inference_py.write_text(source)
    print("LTX_T4_PIPELINE_PATCH=APPLIED",flush=True)

    cfg=SRC/"configs/ltxv-2b-0.9.6-distilled.yaml"
    text=cfg.read_text()
    text=text.replace("prompt_enhancement_words_threshold: 120",
                      "prompt_enhancement_words_threshold: 0")
    cfg.write_text(text)

    OUTDIR.mkdir(parents=True,exist_ok=True)
    gen_started=time.time()
    run([
        sys.executable,"inference.py",
        "--prompt",PROMPT,
        "--height","576",
        "--width","320",
        "--num_frames","81",
        "--frame_rate","24",
        "--seed","632",
        "--offload_to_cpu",
        "--pipeline_config","configs/ltxv-2b-0.9.6-distilled.yaml",
        "--output_path",str(OUTDIR),
    ],cwd=SRC)
    generation_seconds=time.time()-gen_started

    clips=sorted(OUTDIR.glob("*.mp4"),key=lambda p:p.stat().st_mtime)
    if not clips:
        raise SystemExit("KAGGLE_LTX_NO_OUTPUT")
    shutil.copy2(clips[-1],FINAL)

    probe=subprocess.run([
        "ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","stream=codec_name,width,height,r_frame_rate",
        "-show_entries","format=duration,size","-of","json",str(FINAL)
    ],text=True,capture_output=True,check=True)
    meta=json.loads(probe.stdout)
    stream=(meta.get("streams") or [{}])[0]
    fmt=meta.get("format") or {}
    duration=float(fmt.get("duration",0))
    if not stream.get("codec_name") or int(stream.get("height",0)) <= int(stream.get("width",0)) or duration < 3:
        raise SystemExit("KAGGLE_LTX_QC_FAIL="+json.dumps(meta,separators=(",",":")))

    result={
        "status":"PASS",
        "provider":"kaggle_t4x2_ltxv_2b_distilled",
        "model":"ltxv-2b-0.9.6-distilled",
        "gpu_count":len(gpu_lines),
        "gpus":gpu_lines,
        "generation_seconds":round(generation_seconds,3),
        "total_seconds":round(time.time()-started,3),
        "output_duration_seconds":duration,
        "width":int(stream.get("width",0)),
        "height":int(stream.get("height",0)),
        "output":str(FINAL),
        "no_paid_api":True,
    }
    RESULT.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=="__main__":
    main()
