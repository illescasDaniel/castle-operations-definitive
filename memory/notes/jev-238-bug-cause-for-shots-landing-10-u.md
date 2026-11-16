---
name: jev-238-bug-cause-for-shots-landing-10-u
description: On 2026-10-15, rtcw-cod bug cause for shots landing ~10 u above the crosshair while leaning  the camera lean o
type: incident
date: 2026-10-15
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 238, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-15, rtcw-cod bug cause for shots landing ~10 u above the crosshair while leaning: the camera lean offset (cg_view.c) used a roll-tilted right vector (eye dips by |leanf|*sin(roll)) while the server AddLean used an un-rolled one, so the shot origin stayed at full eye height. Fixed with a shared BG_CodLeanOffset (bg_cod.c) used by both, plus fading the viewmodel lean terms in ADS (cg_weapons.c). Gotcha: scripts/build.sh does not copy modules into run/; scripts/install.sh must run or the game keeps the old .so files.

