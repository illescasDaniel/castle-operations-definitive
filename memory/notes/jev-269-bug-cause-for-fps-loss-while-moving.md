---
name: jev-269-bug-cause-for-fps-loss-while-moving
description: "2026-10-22 rtcw-cod bug cause for FPS loss while moving the mouse  rend2 VaoCache (tr_vbo.c) re-memcpy'd and g"
type: incident
date: 2026-10-22
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 269, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-22 rtcw-cod bug cause for FPS loss while moving the mouse: rend2 VaoCache (tr_vbo.c) re-memcpy'd and glBufferSubData'd every batch's vertexes whenever a set of visible surfaces was new, i.e. every frame during view motion (~50 MB/frame on bevelled maps; sunshadow GPU 1.3 -> 8 ms, GPU 3.4 -> 11 ms; still view reuses batches). Fixed by uploading each surface's vertexes + rebased indexes once (hash tables keyed by pointer, reset in RE_LoadWorldMap) and drawing batches with glMultiDrawElements via R_DrawElements/tess.numMultiDraws: moving == still, bench unchanged, shots bit-identical. Harness gotchas: scripted +exec waits break if com_maxfps is 0 at launch (frames fly by during load) and `set` of archived cvars (cg_drawGun, com_maxfps, cl_yawspeed) pollutes wolfconfig.cfg, so back it up and restore; run benchmarks off-screen under gamescope headless.

