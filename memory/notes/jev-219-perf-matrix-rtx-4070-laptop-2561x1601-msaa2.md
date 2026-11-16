---
name: jev-219-perf-matrix-rtx-4070-laptop-2561x1601-msaa2
description: On 2026-10-11, rtcw-cod perf matrix (RTX 4070 Laptop, 2561x1601, MSAA2) showed the game is GPU-bound (~165 FPS
type: gotcha
date: 2026-10-11
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 219, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-11, rtcw-cod perf matrix (RTX 4070 Laptop, 2561x1601, MSAA2) showed the game is GPU-bound (~165 FPS, 720p gives 328); r_depthPrepass 0 / r_forceSun 0 gain +34% only because they disable sun light, shadows and SSAO; MSAA off +28%, SSAO off +13%, shadow map 1024 +9%; r_specularMapping, r_dlightMode, __GL_THREADED_OPTIMIZATIONS and a non-blocking sun query gave 0. Also the ioRTCW engine silently drops command-line '+' commands past MAX_CONSOLE_LINES (32, raised to 64) so extra +set args made +demo vanish and the game sat at the main menu. Never kill the game with SIGKILL: it triggers a system 'launch safely' popup that blocks the next launch.

