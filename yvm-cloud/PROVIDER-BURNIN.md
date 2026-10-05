# YVM Cloud Capacity and Provider Gate

The production requirement is **4x aggregate system headroom**, not quota evasion and not a requirement that every optional provider individually deliver 4x.

## Hard rules

1. No credit card, debit card, ATM card, paid subscription, or automatic paid fallback.
2. Provider quotas and rate limits are respected. We do not rotate identities, accounts, or runners to evade them.
3. The guaranteed baseline must finish even when all optional AI-motion providers fail.
4. The aggregate tested pipeline must have at least 4x capacity for planning, rendering, bilingual TTS, QC, packaging, and retries.
5. Optional AI-motion lanes improve quality but may not become a single point of failure.
6. A provider output must be playable, machine-verifiable, and free of visible provider watermarks before it is accepted.
7. Any provider requiring local heavy GPU inference is excluded from the cloud production path.
8. Failures must be machine-readable so the orchestrator can retain the baseline or select another legitimate lane.

## Verified gates

- 4 complete daily baseline cycles in cloud: PASS.
- 8 final bilingual 1080x1920 outputs across the 4x gate: PASS.
- Keyless LTX motion generation: PASS for individual clips; anonymous quota is too small for 4x, so reserve only.
- Keyless Wan 2.1 base motion generation: PASS for individual clips; capacity measurements continue.
- Wan 2.2 image-to-video: adapter implemented; live gate pending.
- YouTube uploader: implemented with resumable uploads and dry-run validation; live publishing remains locked until OAuth.

## Optional lanes requiring a free credential/session

Agnes, Kaggle, Gemini Web, and Google Flow remain optional expansion lanes. They are not allowed to block the guaranteed no-card baseline.

## Promotion rule

A motion provider can be weighted into automatic production only after real cloud generation, MP4 QC, retry behavior, and legitimate quota behavior are measured. A README claim alone is not accepted as proof.
