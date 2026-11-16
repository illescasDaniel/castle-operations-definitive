---
name: jev-295-frame-warp-ap-r-framewarp-2-verified
description: 2026-10-28 frame warp AP (r_frameWarp 2)  verified pixel-identical real frame vs warp-off at r_aa 4/5/8 (r_aa
type: incident
date: 2026-10-28
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 295, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-28 frame warp AP (r_frameWarp 2): verified pixel-identical real frame vs warp-off at r_aa 4/5/8 (r_aa 8 within noise, needs equal frame parity). Headless AP test needs startup cvars r_frameWarp 2, r_frameWarpApTest 1, r_frameWarpAp 2, com_maxfpsGpuSync 2, com_maxfpsMode 0, com_maxfps 120, r_vsync 0. Use escape1 spot `1808 1600 -759.9 0 0` (spot 3378 460 1104 is free fall). Never `timescale 0` in an MCP console script (hangs 600 s, leaves stale iowolfsp.pid, causes safe-options popup).

