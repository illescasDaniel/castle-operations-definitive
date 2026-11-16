---
name: jev-291-chose-a-depth-tested-quarter-resolution-grid
description: On 2026-10-24, rtcw-cod chose a depth-tested quarter-resolution grid mesh warp (OpenWarp style  vertex-shader
type: preference
date: 2026-10-24
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 291, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-24, rtcw-cod chose a depth-tested quarter-resolution grid mesh warp (OpenWarp style: vertex-shader depth unproject/reproject, min-depth edge bleed, sky z clamp) for the frame-warp 6-DoF stage over per-pixel fixed-point iteration, because occlusion comes from the depth test, cost does not depend on how far the camera moved (predictable warpLead at 240 Hz), and stretched triangles fill disocclusions. The Unity AsyncTimewarp demo and Zee2/openwarp are single-thread "render occasionally, warp every loop" demos; they only work when the real render fits one refresh, so they give no answer for the AP pacer (still needs cooperative checkpoints).

