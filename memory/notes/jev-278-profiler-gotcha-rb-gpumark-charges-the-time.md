---
name: jev-278-profiler-gotcha-rb-gpumark-charges-the-time
description: "2026-10-23 rtcw-cod profiler gotcha  RB_GpuMark charges the time since the previous mark to the named bucket."
type: incident
date: 2026-10-23
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 278, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-23 rtcw-cod profiler gotcha: RB_GpuMark charges the time since the previous mark to the named bucket. After engine 1baed4a9 (AO multiply moved between opaque and translucent lists) no mark followed the opaque draw, so gpuprof `ssao_apply` showed ~1.33 ms at 2560x1600 but was ~1.1 ms opaque scene + ~0.25 ms real AO blit (near bandwidth floor, not worth optimising). Fixed with a `scene_opaque` mark. Opaque pass A/B: parallax ~0.59 ms of 1.18, specular ~0.30, cubemaps/dlights ~0.

