---
name: jev-257-bug-cause-for-dark-wall-floor-corners
description: On 2026-10-16, rtcw-cod bug cause for dark wall/floor corners showing through fog volumes (escape1 corridor)
type: incident
date: 2026-10-16
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 257, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-16, rtcw-cod bug cause for dark wall/floor corners showing through fog volumes (escape1 corridor): rend2 draws the q3 fog-volume pass (RB_FogPass(0)) inside the opaque list, blending fog into the lit color, and the multiply AO applied afterwards darkened the fog itself. Fix: when AO applies, backEnd.fogDefer skips the fog pass in the opaque list, then a second RB_RenderDrawSurfList over only the fogged opaque surfaces runs with backEnd.fogOnly after the AO blit. Map-wide RTCW glfog is handled differently: ssaoup_fp.glsl scales AO by the fog factor via u_FogDepth (start,end,density,mode).

