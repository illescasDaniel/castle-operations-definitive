---
name: jev-229-flashlight-shadows-2026-10-13-r-dlightmode
description: Flashlight shadows (2026-10-13)  r_dlightMode 2 cube shadows are broken, so the flashlight uses one spot shado
type: incident
date: 2026-10-13
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 229, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

Flashlight shadows (2026-10-13): r_dlightMode 2 cube shadows are broken, so the flashlight uses one spot shadow map (REF_SHADOW_DLIGHT, R_RenderFlashlightShadowMap) plus a screen-space R8 mask sampled via the TB_AOMAP unit (u_AoParams.y). The local player's body/weapon must be excluded (VPF_NOPLAYER) or they show up as buggy shadows. r_flashlightShadow 2 shows the mask inset.

