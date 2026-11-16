---
name: jev-161-uncapped-fps-by-default-with-seta-com
description: "On 2026-10-09, codmod uncapped FPS by default with seta com_maxfps \"0\" in mod/codmod/codmod.cfg only, because"
type: decision
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 161, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, codmod uncapped FPS by default with seta com_maxfps "0" in mod/codmod/codmod.cfg only, because ioRTCW already treats com_maxfps <= 0 as no frame sleep cap and a common.c default change would also affect --vanilla.

