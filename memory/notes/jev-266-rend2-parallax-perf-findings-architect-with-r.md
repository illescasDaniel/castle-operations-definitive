---
name: jev-266-rend2-parallax-perf-findings-architect-with-r
description: "2026-10-22 rtcw-cod rend2 parallax perf findings (architect)  with r_sunlightMode 1 the POM sun self-shadow ma"
type: gotcha
date: 2026-10-22
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 266, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-22 rtcw-cod rend2 parallax perf findings (architect): with r_sunlightMode 1 the POM sun self-shadow march (up to 24 fetches/pixel) only darkens sun specular; USE_PARALLAXMAP compiles only inside the r_normalMapping block, so parallax needs r_normalMapping 1; r_ext_compressed_textures is 0 so _n/_nh are uncompressed RGBA8 with AF16 in every march fetch; height-bake FLAT textures still keep up to ~15% depth in alpha and run the full march. Bench (1920x1200): normals off 278 fps, normals on 263, normals+relief+shadows 196.

