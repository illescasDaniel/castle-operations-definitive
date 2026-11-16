---
name: jev-218-rebuilt-its-benchmark-as-real-time-demo
description: On 2026-10-11, rtcw-cod rebuilt its benchmark as real-time demo replay (cl_benchDemo 1 + plain `demo codmod_be
type: decision
date: 2026-10-11
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 218, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-11, rtcw-cod rebuilt its benchmark as real-time demo replay (cl_benchDemo 1 + plain `demo codmod_bench`, per-frame µs stats in cl_cgame.c/cl_main.c, scripts/bench.sh) because stock `timedemo 1` steps 50 ms of game time per frame, collapsing the ~23 s demo into 503 frames in 3.6 s (too few for 1% lows). No renderer, cl_scrn or camera changes.

