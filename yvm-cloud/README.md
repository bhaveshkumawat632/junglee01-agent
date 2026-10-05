# YVM Cloud — No-Card Automation

This directory is an isolated cloud migration path for the YouTube Viral Machine.
It does not modify the existing local YVM scripts or services.

## Hard policy

- Payment card / debit card / ATM card: NEVER required, NEVER requested.
- No paid fallback.
- No automatic upgrade to paid plans.
- Any provider that requires billing details is disqualified.
- A claimed "free" provider is not considered reliable until measured.
- Existing protected local YVM V4/V5 files and services remain untouched.

## Current verified state

### PASS
- GitHub Actions cloud orchestration and FFmpeg
- 4x bilingual render burn-in: 4 cycles / 8 MP4 outputs
- English + Hindi Edge TTS separation and QC
- No-key LLM7 live model discovery and inference
- 12-scene bilingual daily planning
- Google Trends + Google News research feeds
- Keyless Pollinations image generation
- Wikimedia Commons licensed-media fallback
- One public LTX-2.5 ZeroGPU video generation with valid H.264/AAC output
- YouTube OAuth uploader code is ready, but production upload is intentionally disabled

### DEGRADED / RESERVE ONLY
- Hugging Face LTX ZeroGPU: single generation works, but the legitimate same-runner sequential capacity test hit the anonymous ZeroGPU quota on cycle 3. It is a bonus/rescue lane, not the 4x backbone.
- DeepRat LTX ZeroGPU: API discovery works; live generation currently returns a runtime error, so it is disabled from production weighting.
- Pollinations legacy text route: intermittent 500 error; LLM7 is the active keyless planner instead.

### READY BUT REQUIRES FREE ACCOUNT CREDENTIAL
- Agnes AI video: adapter implemented. The service requires a free Agnes API key; no payment card is part of the design.
- Kaggle GPU: reserved as an open-model GPU lane when a Kaggle credential is available.
- Gemini Web / Google Flow: reserved for browser-session quality upgrades when a cloud-authenticated browser session is available.

## Production architecture

1. Research: Google Trends + Google News.
2. Script/scene planner: keyless LLM7; deterministic fallback if unavailable.
3. Guaranteed visual baseline:
   - keyless AI images first,
   - Wikimedia Commons for any missing visual,
   - CPU motion rendering in GitHub Actions.
4. Video enhancement:
   - Agnes when configured,
   - legitimate small ZeroGPU bonus where quota allows,
   - baseline is retained if video enhancement fails.
5. Stitch and normalize to 1080x1920 H.264.
6. Render separate English and Hindi AAC voice tracks.
7. QC duration, resolution, codecs and audio.
8. Upload both videos to YouTube only after OAuth is explicitly connected.

## Capacity rule

The guaranteed path must continue working even if every optional GPU/video provider fails.
The 4x infrastructure/render gate already passed. Optional AI video providers never block a daily upload.

## Production switch

`.github/workflows/yvm-daily-production.yml` exists but has no cron schedule yet.
YouTube posting is gated behind `YVM_PRODUCTION_ENABLED=true`.
The intended schedule after final authorization is 21:00 IST (15:30 UTC).

The remaining external authorization for publishing is YouTube OAuth:
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

Do not commit these values to the repository.
