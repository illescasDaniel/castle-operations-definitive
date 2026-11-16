---
name: jev-302-ap-heavy-load-fix-uncommitted-at-time
description: "2026-11-04  AP heavy-load fix (uncommitted at time of note). Root causes  (1) Com_ApBacklog assumed unresolved"
type: incident
date: 2026-11-04
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 302, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-11-04: AP heavy-load fix (uncommitted at time of note). Root causes: (1) Com_ApBacklog assumed unresolved GPU work costs its CPU submit time; with r_sunShadowCascadeUpdate 2 (user pins it) per-checkpoint GPU cost alternates by frame parity, mispredicting ~+2.4 ms, so 40% of frames got no warp. Fixed by a learned per-(shape,where,ord) GPU-offset profile (r_frameWarpModel). (2) Above busy ~0.93*2*T1 the S step-down controller capped real frames 20-25% below GPU capability; fixed by a GPU-paced regime (r_frameWarpGpuPaced): S stays sMax, real frames at GPU rate, one midpoint warp. Gotchas: judge AP on gpuclk_distinct_per_s (swap clock overstates under GPU-heavy load, swap returns 0.6-9 ms before GPU done; revises the 2026-10-31 swap-clock choice for deny/stats); feed deny window max(swap return, GPU done); r_frameWarpBacklogUs 1000/1500 made things worse; AP_PROF_REAL/lastRealG were never fed originally; enter threshold 0.97 left a dead zone (use 0.93/0.88); headless refresh reads 60 so pin r_frameWarpHz 233; measure each heavy cell in a fresh run (controller state persists). Result at escape1 1346 160 -620 0: L4500 c2 214 distinct/s vs late-latch bar 111, stable, no deny trials.

