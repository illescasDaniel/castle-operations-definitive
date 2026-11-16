---
name: jev-232-found-why-the-gpu-was-only-76
description: On 2026-10-14, rtcw-cod found why the GPU was only ~76-80% busy uncapped  stock rend2 RB_SwapBuffers called gl
type: incident
date: 2026-10-14
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 232, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-14, rtcw-cod found why the GPU was only ~76-80% busy uncapped: stock rend2 RB_SwapBuffers called glFinish every frame (CPU/GPU serialized) and RB_TestFlare did a glReadPixels depth readback per flare, which stalls the NVIDIA GPU even when read async into a PBO with a fence. Fixed with r_swapFinish 0 (default) and per-flare GL_SAMPLES_PASSED occlusion queries keyed by flare id/scene/portal (r_flaresAsync 1). Bench 183 -> 247 FPS, 1% low 106 -> 165, GPU 97%. The earlier 'non-blocking sun query gave 0' result was masked by the glFinish but still gives 0 after removing it.

