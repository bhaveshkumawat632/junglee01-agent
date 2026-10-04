# YVM Cloud — No-Card Automation

This directory is an isolated cloud migration path for the YouTube Viral Machine.
It does not modify the existing local YVM scripts or services.

## Hard policy

- Payment card / debit card / ATM card: NEVER required, NEVER requested.
- No paid fallback.
- No auto-upgrade to paid plans.
- Any provider that asks for billing details is immediately disqualified.
- Production providers must demonstrate at least 4x the measured capacity of one complete daily cycle.
- A provider is not considered production-ready merely because a README says "free" or "unlimited".
- Existing protected YVM V4/V5 files and local services are untouched.

## Candidate provider pool

1. Agnes AI cloud video
2. Kaggle free GPU
3. Gemini Web session bridge
4. Google Flow browser/MCP automation
5. Hugging Face ZeroGPU

All five are treated as independent capacity/failover lanes. Each must pass a real no-card preflight and 4x burn-in before production weighting.

## Orchestration

GitHub Actions on this public repository is the card-free scheduler/render/QC layer.
The first validation is a four-cycle bilingual burn-in:
- 4 independent cycles
- English TTS + Hindi TTS
- 8 total vertical MP4 outputs
- distinct EN/HI audio hashes
- ffprobe validation
- artifact upload

The production daily schedule remains disabled until generator and YouTube-auth preflights pass.
