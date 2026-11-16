---
name: jev-307-mesa-intel-s-glsl-compiler-rejected-rtcw
description: On 2026-11-06 Mesa Intel's GLSL compiler rejected rtcw-cod's SSAO upsample shader because its texture gather e
type: incident
date: 2026-11-06
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 307, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-11-06 Mesa Intel's GLSL compiler rejected rtcw-cod's SSAO upsample shader because its texture gather extension directive followed the generated fragment output declaration; moving the directive into the shader header before declarations fixes the ordering.

