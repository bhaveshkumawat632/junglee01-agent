# Provider 4x Burn-In Gate

A provider is promoted from candidate to production only when all checks pass without payment-card details.

## Required checks
1. Account/API/session can be created without card details.
2. Four complete video-generation cycles are executed.
3. At least one intentional retry/failover is exercised.
4. Downloaded output is playable MP4.
5. No visible provider watermark is present.
6. Character/reference consistency is acceptable for the target workflow.
7. Average measured capacity is at least 4x one daily production cycle.
8. No local heavy GPU inference is required.
9. Provider can be called unattended or through a stable signed-in browser/session automation.
10. Failure must return a machine-readable status so the next provider can be selected.

## Production order
Agnes -> Kaggle -> Gemini Web -> Google Flow -> Hugging Face ZeroGPU

No provider may silently fall back to a paid tier.
