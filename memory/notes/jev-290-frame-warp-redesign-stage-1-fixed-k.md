---
name: jev-290-frame-warp-redesign-stage-1-fixed-k
description: On 2026-10-24, rtcw-cod frame warp redesign  Stage 1 fixed-k pacer gives a real frame only T (not kT) on one t
type: decision
date: 2026-10-24
status: superseded
supersedes: 
superseded_by: jev-293-ap-r-framewarp-2-design-cooperative-checkpoints
source:
---

Historical jevmem entry 290, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-24, rtcw-cod frame warp redesign: Stage 1 fixed-k pacer gives a real frame only T (not kT) on one thread, because warp slots sit between real deadlines, so the lead>T suspension at 240/120, 120/60, 60/30 is structural (plus glFinish-serialized CPU+GPU timing and GPU downclock when capped). Chosen redesign: "compositor in the main thread" (r_frameWarp 2): real frames uncapped and skip their own present, every present is a warp of the newest capture at refresh slots, cooperative checkpoints + fence-bounded GPU backlog. Order: late-latch (r_frameWarp 1, sample at end of RB_PostProcess, no pacer) -> adaptive pacer (spike first) -> depth 6-DoF reprojection -> entity motion. Gotchas: a deliberate pre-swap wait must not be recorded in pacer.ring (lead inflates every frame); SMAA T2x velocity buffer exists only at r_aa 8 (default r_aa 4). User's real case: ~150 fps uncapped on escape1 maxed at native res, wants a steady monitor-Hz.

