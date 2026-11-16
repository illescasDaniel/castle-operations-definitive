---
name: jev-230-fixed-static-md3-props-escape1-skeleton-cages
description: "On 2026-10-13, rtcw-cod fixed static MD3 props (escape1 skeleton cages, iron gates) being unlit by the flashli"
type: incident
date: 2026-10-13
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 230, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-13, rtcw-cod fixed static MD3 props (escape1 skeleton cages, iron gates) being unlit by the flashlight. Cause was three rend2 gaps, not the material: VAO surfaces draw inside the rb_surfaceTable call, so tess.dlightBits must be ORed with needDlights before the call; RB_EndSurface/RB_BeginSurface restarts zeroed tess.dlightBits; ForwardDlight used the world lightall variant without LIGHTDEF_ENTITY_VERTEX_ANIMATION/BONE_ANIMATION, so u_ModelMatrix was skipped and model-space vertices missed the world-space light. r_dlightAlbedoLift was a red herring (default 1 = off).

