---
name: jev-221-replaced-msaa-2x-with-smaa-1x-high
description: "On 2026-10-12, rtcw-cod replaced MSAA 2x with SMAA 1x High (r_smaa 3, MSAA 0) as the default AA  a rend2 pass"
type: decision
date: 2026-10-12
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 221, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-12, rtcw-cod replaced MSAA 2x with SMAA 1x High (r_smaa 3, MSAA 0) as the default AA: a rend2 pass inside RB_PostProcess after tonemap and before 2D, so RB_SwapBuffers is untouched. Bench at 2561x1601: SMAA3 225 FPS vs MSAA2 190 (+18%), no AA 261. SMAA is inactive when r_hdr 0 and MSAA is off (no FBO). Source vendored from iryoku/smaa (MIT), credited in docs/credits.md.

