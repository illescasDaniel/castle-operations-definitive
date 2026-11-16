---
name: jev-146-wall-pom-smoke-test-uses-iortcw-rend2
description: On 2026-10-09, rtcw-cod wall POM smoke test uses ioRTCW rend2 (not opengl1)  offline tools/pom-bake builds RGB
type: decision
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 146, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, rtcw-cod wall POM smoke test uses ioRTCW rend2 (not opengl1): offline tools/pom-bake builds RGBA *_nh.png (RGB normal, alpha height) from HD diffuse, shipped in local codmod_pom.pk3 with scripts/codmod_pom.mtr; cl_renderer and r_parallaxMapping are CVAR_LATCH so scripts/run.sh +sets them before InitRef in addition to seta in codmod.cfg.

