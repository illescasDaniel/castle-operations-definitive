---
name: jev-258-bug-cause-for-specular-highlights-dropping-bench
description: On 2026-10-17, rtcw-cod bug cause for specular highlights dropping bench FPS 274 -> 141  rend2 turns every ai_
type: incident
date: 2026-10-17
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 258, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-17, rtcw-cod bug cause for specular highlights dropping bench FPS 274 -> 141: rend2 turns every ai_marker into a cubemap probe (164 on escape2) and RB_RenderDrawSurfList ends a draw batch whenever drawSurf->cubemapIndex changes, though it is not in the sort key; batches/frame went 600 -> 3500 (sunshadow GPU pass 0.4 -> 4.1 ms, not fill-bound). Fixed in rend2: R_AddDrawSurf zeroes cubemap for shadow/depth/unlit/non-spec-map shaders (r_cubemapSpecOnly), radix pass groups by cubemap, R_ClusterCubemaps merges ai_marker probes (r_cubemapMergeDist 384, 164 -> 33) -> 267 FPS. Gotcha: bench.sh --set with a while-read loop eats stdin; use </dev/null.

