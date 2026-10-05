#!/usr/bin/env python3
"""Kaggle dual-T4 multi-scene capacity worker for YVM Cloud.

Runs four real LTX-Video 2B distilled generations in one Kaggle kernel so model
downloads/install happen once per capacity run. Each scene is independently
generated and measured. No paid API is used.
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
RESULT=WORK/"yvm_kaggle_capacity_result.json"

PROMPTS=[
    "A cinematic documentary exterior of the New York financial district in the early 1990s at dawn, traders in period business clothing walking quickly toward office towers, slow forward camera movement, realistic film lighting, authentic era, no logos, no readable text, no watermark, vertical composition.",
    "Inside a crowded 1990s Wall Street trading floor, adult professional traders move between desks with CRT monitors and telephones, energetic hand gestures, camera glides between desks, realistic human motion, documentary cinematography, no logos, no readable text, no watermark, vertical composition.",
    "Close cinematic shot of a 1990s stock trader rapidly working two desk telephones while market papers move in the background, shallow depth of field, handheld documentary camera movement, realistic office lighting, no logos, no readable text, no watermark, vertical composition.",
    "After-hours 1990s financial office with CRT screens glowing while a small team studies market charts and printed sheets, camera slowly arcs around the group, realistic human motion, dramatic practical lighting, no logos, no readable text, no watermark, vertical composition.",
]

def run(cmd,cwd=None):
    print("+"," ".join(map(str,cmd)),flush=True)
    subprocess.run([str(x) for x in cmd],cwd=cwd,check=True)

def patch_ltx():
    inference_py=SRC/"ltx_video/inference.py"
    source=inference_py.read_text()
    replacements=[
        (
            '''    text_encoder = T5EncoderModel.from_pretrained(
        text_encoder_model_name_or_path, subfolder="text_encoder"
    )''',
            '''    text_encoder = T5EncoderModel.from_pretrained(
        text_encoder_model_name_or_path,
        subfolder="text_encoder",
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
    )''',
            "text_encoder_bf16",
        ),
        (
            '''    transformer = transformer.to(device)
    vae = vae.to(device)
    text_encoder = text_encoder.to(device)
''',
            '''    transformer = transformer.to(device)
    vae = vae.to(device)
    text_encoder_device = (
        "cuda:1"
        if torch.cuda.is_available() and torch.cuda.device_count() > 1
        else "cpu"
    )
    text_encoder = text_encoder.to(text_encoder_device)
''',
            "dual_gpu_initial_placement",
        ),
        (
            '''    pipeline = LTXVideoPipeline(**submodel_dict)
    pipeline = pipeline.to(device)
    return pipeline''',
            '''    pipeline = LTXVideoPipeline(**submodel_dict)
    return pipeline''',
            "avoid_pipeline_wide_cuda_move",
        ),
    ]
    for old,new,label in replacements:
        if old not in source:
            raise RuntimeError(f"LTX_PATCH_TARGET_MISSING={label}")
        source=source.replace(old,new,1)
    inference_py.write_text(source)

    pipeline_py=SRC/"ltx_video/pipelines/pipeline_ltx_video.py"
    psource=pipeline_py.read_text()
    replacements=[
        (
            '''        device = self._execution_device

        self.video_scale_factor''',
            '''        device = (
            torch.device("cuda:0")
            if torch.cuda.is_available()
            else self._execution_device
        )

        self.video_scale_factor''',
            "generation_device_cuda0",
        ),
        (
            '''            prompt_attention_mask = text_inputs.attention_mask
            prompt_attention_mask = prompt_attention_mask.to(text_enc_device)
            prompt_attention_mask = prompt_attention_mask.to(device)

            prompt_embeds = self.text_encoder(
                text_input_ids.to(text_enc_device), attention_mask=prompt_attention_mask
            )
            prompt_embeds = prompt_embeds[0]''',
            '''            prompt_attention_mask = text_inputs.attention_mask.to(text_enc_device)

            prompt_embeds = self.text_encoder(
                text_input_ids.to(text_enc_device), attention_mask=prompt_attention_mask
            )
            prompt_embeds = prompt_embeds[0]
            prompt_attention_mask = prompt_attention_mask.to(device)''',
            "positive_prompt_device_transfer",
        ),
        (
            '''            negative_prompt_embeds = self.text_encoder(
                uncond_input.input_ids.to(text_enc_device),
                attention_mask=negative_prompt_attention_mask,
            )
            negative_prompt_embeds = negative_prompt_embeds[0]''',
            '''            negative_prompt_embeds = self.text_encoder(
                uncond_input.input_ids.to(text_enc_device),
                attention_mask=negative_prompt_attention_mask,
            )
            negative_prompt_embeds = negative_prompt_embeds[0]
            negative_prompt_attention_mask = negative_prompt_attention_mask.to(device)''',
            "negative_prompt_device_transfer",
        ),
        (
            '''        if self.text_encoder is not None:
            self.text_encoder = self.text_encoder.to(self._execution_device)''',
            '''        # YVM: keep the text encoder on cuda:1 (or CPU fallback).''',
            "preserve_text_encoder_device",
        ),
        (
            '''        self.transformer = self.transformer.to(self._execution_device)''',
            '''        self.transformer = self.transformer.to(device)''',
            "transformer_cuda0",
        ),
    ]
    for old,new,label in replacements:
        if old not in psource:
            raise RuntimeError(f"LTX_PIPELINE_PATCH_TARGET_MISSING={label}")
        psource=psource.replace(old,new,1)
    pipeline_py.write_text(psource)
    print("LTX_T4_DUAL_GPU_PATCH=APPLIED",flush=True)

def probe(path):
    p=subprocess.run([
        "ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","stream=codec_name,width,height,r_frame_rate",
        "-show_entries","format=duration,size","-of","json",str(path)
    ],text=True,capture_output=True,check=True)
    return json.loads(p.stdout)

def main():
    os.environ["PYTORCH_CUDA_ALLOC_CONF"]="expandable_segments:True"
    started=time.time()
    gpu=subprocess.run(
        ["nvidia-smi","--query-gpu=name,memory.total","--format=csv,noheader"],
        text=True,capture_output=True
    )
    if gpu.returncode:
        raise SystemExit("KAGGLE_GPU_NOT_AVAILABLE")
    gpu_lines=[line.strip() for line in gpu.stdout.splitlines() if line.strip()]
    print("GPUS=\n"+gpu.stdout,flush=True)
    if len(gpu_lines)<2:
        raise SystemExit(f"KAGGLE_T4X2_REQUIRED gpu_count={len(gpu_lines)}")

    if not SRC.exists():
        run(["git","clone","--depth","1","https://github.com/Lightricks/LTX-Video.git",SRC])
    patch_ltx()
    run([sys.executable,"-m","pip","install","-q","-e",".[inference]","accelerate"],cwd=SRC)

    cfg=SRC/"configs/ltxv-2b-0.9.6-distilled.yaml"
    text=cfg.read_text().replace(
        "prompt_enhancement_words_threshold: 120",
        "prompt_enhancement_words_threshold: 0"
    )
    cfg.write_text(text)

    clips=[]
    for idx,prompt in enumerate(PROMPTS,1):
        outdir=WORK/f"ltx_scene_{idx:02d}"
        outdir.mkdir(parents=True,exist_ok=True)
        t0=time.time()
        run([
            sys.executable,"inference.py",
            "--prompt",prompt,
            "--height","576",
            "--width","320",
            "--num_frames","81",
            "--frame_rate","24",
            "--seed",str(632+idx),
            "--offload_to_cpu",
            "--pipeline_config","configs/ltxv-2b-0.9.6-distilled.yaml",
            "--output_path",str(outdir),
        ],cwd=SRC)
        elapsed=time.time()-t0
        generated=sorted(outdir.glob("*.mp4"),key=lambda p:p.stat().st_mtime)
        if not generated:
            raise SystemExit(f"KAGGLE_LTX_NO_OUTPUT scene={idx}")
        final=WORK/f"yvm_kaggle_scene_{idx:02d}.mp4"
        shutil.copy2(generated[-1],final)
        meta=probe(final)
        stream=(meta.get("streams") or [{}])[0]
        fmt=meta.get("format") or {}
        duration=float(fmt.get("duration",0) or 0)
        width=int(stream.get("width",0) or 0)
        height=int(stream.get("height",0) or 0)
        if not stream.get("codec_name") or height<=width or duration<3:
            raise SystemExit(f"KAGGLE_LTX_QC_FAIL scene={idx} meta={json.dumps(meta,separators=(',',':'))}")
        clips.append({
            "scene":idx,
            "output":final.name,
            "generation_seconds":round(elapsed,3),
            "duration_seconds":duration,
            "width":width,
            "height":height,
            "seed":632+idx,
        })
        print("SCENE_RESULT="+json.dumps(clips[-1],separators=(",",":")),flush=True)

    generation_total=sum(x["generation_seconds"] for x in clips)
    result={
        "status":"PASS",
        "provider":"kaggle_t4x2_ltxv_2b_distilled",
        "model":"ltxv-2b-0.9.6-distilled",
        "gpu_count":len(gpu_lines),
        "gpus":gpu_lines,
        "scene_count":len(clips),
        "generation_seconds_total":round(generation_total,3),
        "generation_seconds_avg":round(generation_total/len(clips),3),
        "total_seconds":round(time.time()-started,3),
        "clips":clips,
        "no_paid_api":True,
    }
    RESULT.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=="__main__":
    main()
