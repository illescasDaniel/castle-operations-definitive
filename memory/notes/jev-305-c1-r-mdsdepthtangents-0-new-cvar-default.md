---
name: jev-305-c1-r-mdsdepthtangents-0-new-cvar-default
description: "2026-11-05 rtcw-cod C1  r_mdsDepthTangents 0 (new cvar, default 1 = old) skips MDS tangent computation in dept"
type: incident
date: 2026-11-05
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 305, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-11-05 rtcw-cod C1: r_mdsDepthTangents 0 (new cvar, default 1 = old) skips MDS tangent computation in depth-fill passes (backEnd.depthFill = sun shadow cascades + depth prepass; no depth program reads tangents). Escape2 bench ABBA (r_frameWarp 0, 4 legs): profiler-off FPS 240.6 -> 255.4 (+6.2%), 1% low 145.8 -> 184.1; profiler-on sunshadow 0.601 -> 0.315 ms, GPU mean -8.8%, P99 -24%. Confirms the GPU starves behind CPU MDS depth assembly. Default not flipped yet (needs user in-game check). compare_shots cannot prove pixel identity on escape2 (same-build diffs 0.1-5.7 mean abs); rely on the audit. Profile legs' cvars.csv only lists a fixed cvar list.

