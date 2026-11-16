---
name: jev-301-headless-repro-of-the-user-s-heavy
description: "2026-11-04  Headless repro of the user's heavy cage view  escape1 spot `1346 160 -620 0 0` (cage origin 1646 1"
type: gotcha
date: 2026-11-04
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 301, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-11-04: Headless repro of the user's heavy cage view: escape1 spot `1346 160 -620 0 0` (cage origin 1646 160 -676) with r_aa 8 and `r_gpuLoad 3000` (busy about 8.5 ms per real frame, matching the user's 8.8 ms at 2560x1600). AP then steps slot 197 -> 174 -> 153 (real 76-98 fps) and delivers 107-112 distinct/s, while measured late-latch gives about 119/s, so the deny trial fires (AP off 30 s, then retries). Unloaded at 1920x1200 the same spot is 5.8 ms busy, slot 233 steady, 211 distinct/s. Cause: at busy >= ~7 ms per real frame AP (k=2 slot structure plus mesh warp cost) delivers fewer distinct frames than plain late-latch. Harness caveat: com_maxfps 120 caps the late-latch side at 120.

