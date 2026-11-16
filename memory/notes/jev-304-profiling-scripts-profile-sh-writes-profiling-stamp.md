---
name: jev-304-profiling-scripts-profile-sh-writes-profiling-stamp
description: "2026-11-05 rtcw-cod profiling  scripts/profile.sh writes profiling/<stamp>-<label>/ (mode1 r_gpuProfile 1, mod"
type: incident
date: 2026-11-05
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 304, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-11-05 rtcw-cod profiling: scripts/profile.sh writes profiling/<stamp>-<label>/ (mode1 r_gpuProfile 1, mode2 = per-shader, ~8% slower). Stats must use the bench window (cl_benchMeasuring cvar set by the client; renderer reads it). bench.sh gotcha: under set -e, an EXIT trap ending in `[[ -n x ]] && kill ...` aborts with exit 1 when kill fails; use if/|| true. Baseline framewarp-off-v2: 229.9 fps, GPU 4.25 ms; MDS tangent CPU 0.79 ms/frame, 89% in depth-fill passes.

