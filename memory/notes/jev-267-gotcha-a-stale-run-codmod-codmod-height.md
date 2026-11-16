---
name: jev-267-gotcha-a-stale-run-codmod-codmod-height
description: "2026-10-22 rtcw-cod gotcha  a stale run/codmod/codmod_height_legacy.pk3 sorts after codmod_height.pk3 and sile"
type: incident
date: 2026-10-22
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 267, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-22 rtcw-cod gotcha: a stale run/codmod/codmod_height_legacy.pk3 sorts after codmod_height.pk3 and silently overrides the real height pack, making walls look shredded; delete stale pk3s before judging heights. Screenshot tips: escape1 starts with a cutscene, skip with `cmd cameraInterrupt` (SHOT_PRE in scripts/shot-at.sh); SHOT_HEADLESS=1 runs under gamescope headless; bench.sh also works inside `gamescope --backend headless --`.

