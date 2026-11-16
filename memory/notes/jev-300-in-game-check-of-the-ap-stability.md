---
name: jev-300-in-game-check-of-the-ap-stability
description: 2026-10-31  In-game check of the AP stability rework (commits iortcw bfdbc1c3 / outer 8734f03) on the user's h
type: gotcha
date: 2026-10-31
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 300, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-31: In-game check of the AP stability rework (commits iortcw bfdbc1c3 / outer 8734f03) on the user's heavy cage view was mediocre: overlay 110-180 fps fluctuating, GPU load 60-80% (not saturated), 1% low 43, 0.1% low 4 (RTX 4070 laptop, 2560x1600, T2x, fullscreen VRR 240 Hz). Their apstats (taken from the menu, 14.85 s window): slot 167 k=2 so real cap 83.6, real_fps 87, downs=2 ups=0, distinct_per_s 158.5 (swap clock), ll_est 120, busy_us_per_real 8774 (GPU could do ~114 real fps, above the 84 cap), baseline 8175, r>r kind 213 of 1294 (16% real frames with no warp after), iv_gt1p5T 9.5%, misses 2, trials 0, no deny. Headless r_gpuLoad scenario passed but did not predict this; GPU under 80% suggests the limit is pacing/CPU-side or the k=2 slot cap, not GPU saturation. Not yet known whether the rework is worse than the previous build (~180-205 fps before the cage view). Fix deferred, user out of usage.

