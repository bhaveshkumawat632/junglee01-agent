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
    "1992 Wall Street trading floor documentary footage, crowded financial office, "
    "adult professional traders in dark suits and suspenders moving urgently between desks, "
    "bulky beige CRT cathode-ray-tube monitors with curved glass, corded landline telephones, "
    "paper ticker sheets and printed market reports, authentic early-1990s fluorescent office lighting, "
    "slow forward camera push with realistic human motion, subtle 35mm film texture, "
    "no laptops, no flat-panel LCD screens, no smartphones, no modern LED office design, "
    "no logos, no readable text, no watermark, vertical composition."
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

    # Patch upstream LTX for Kaggle's two 15 GiB T4 GPUs.
    # Upstream moves transformer + VAE + the large T5 encoder onto one GPU,
    # which OOMs before generation begins. Put the T5 encoder on cuda:1 in
    # BF16, keep transformer/VAE on cuda:0, and move prompt tensors back to
    # cuda:0 after encoding.
    inference_py=SRC/"ltx_video/inference.py"
    source=inference_py.read_text()

    source_replacements=[
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
    for old,new,label in source_replacements:
        if old not in source:
            raise RuntimeError(f"LTX_PATCH_TARGET_MISSING={label}")
        source=source.replace(old,new,1)
    inference_py.write_text(source)

    pipeline_py=SRC/"ltx_video/pipelines/pipeline_ltx_video.py"
    psource=pipeline_py.read_text()
    pipeline_replacements=[
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
            '''        # YVM: text encoder already lives on cuda:1 (or CPU fallback).
        # Do not move it onto cuda:0 before prompt encoding.''',
            "preserve_text_encoder_device",
        ),
        (
            '''        self.transformer = self.transformer.to(self._execution_device)''',
            '''        self.transformer = self.transformer.to(device)''',
            "transformer_cuda0",
        ),
    ]
    for old,new,label in pipeline_replacements:
        if old not in psource:
            raise RuntimeError(f"LTX_PIPELINE_PATCH_TARGET_MISSING={label}")
        psource=psource.replace(old,new,1)
    pipeline_py.write_text(psource)
    print("LTX_T4_DUAL_GPU_PATCH=APPLIED",flush=True)

    # Official inference dependencies.
    run([sys.executable,"-m","pip","install","-q","-e",".[inference]","accelerate"],cwd=SRC)


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
