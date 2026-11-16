---
name: jev-234-rend2-gtao-finding-per-pixel-random-slice
description: "2026-10-14 rend2 GTAO finding  per-pixel random slice directions make far GTAO taps miss the texture cache (co"
type: gotcha
date: 2026-10-14
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 234, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-14 rend2 GTAO finding: per-pixel random slice directions make far GTAO taps miss the texture cache (constant noise was 2.4x faster). Reading far taps from point-sampled half-res depth mips (XeGTAO style, r_ssaoDepthMips) cut ssao_ao from 0.78 to 0.49 ms with visually identical output (not bit-exact).

