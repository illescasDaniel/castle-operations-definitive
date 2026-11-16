---
name: jev-147-iortcw-rend2-only-discovers-mtr-materials-when
description: On 2026-10-09, ioRTCW rend2 only discovers .mtr materials when a same-basename .shader exists under scripts/ (
type: incident
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 147, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, ioRTCW rend2 only discovers .mtr materials when a same-basename .shader exists under scripts/ (FS_ListFiles lists .shader then prefers .mtr); rtcw-cod ships a stub scripts/codmod_pom.shader so codmod_pom.mtr loads.

