---
name: jev-233-rend2-gotcha-stock-rb-updatesunflarevis-read-the
description: "2026-10-14 rend2 gotcha  stock RB_UpdateSunFlareVis read the previous frame's sun occlusion query with a block"
type: incident
date: 2026-10-14
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 233, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-14 rend2 gotcha: stock RB_UpdateSunFlareVis read the previous frame's sun occlusion query with a blocking GL_QUERY_RESULT (a CPU/GPU sync each frame), and counted not-ready results as visible, so the sun-ray passes ran on almost every frame even indoors. Fixed with a 4-query ring read only when available.

