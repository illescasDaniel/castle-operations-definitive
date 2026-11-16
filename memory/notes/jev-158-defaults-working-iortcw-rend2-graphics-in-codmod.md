---
name: jev-158-defaults-working-iortcw-rend2-graphics-in-codmod
description: "On 2026-10-09, rtcw-cod defaults working ioRTCW rend2 graphics in codmod.cfg and scripts/run.sh latch +sets  r"
type: decision
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 158, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, rtcw-cod defaults working ioRTCW rend2 graphics in codmod.cfg and scripts/run.sh latch +sets: r_ext_framebuffer_multisample 2, r_ext_texture_filter_anisotropic 16, r_floatLightmap 1, r_specularMapping 1, r_deluxeMapping 1, r_forceSun 1, r_drawSunRays 1, r_shadowFilter 2, r_shadowMapSize 2048, plus existing r_ssao 1 and r_dlightMode 1; skipped r_dlightMode 2 (broken), r_bloom (opengl1-only), r_pbr, cubemaps, imageUpsample, genNormalMaps, r_sunlightMode 2, and parallax/normals.

