---
name: jev-162-phase-6b-prone-tier-a-was-implemented
description: "On 2026-10-09, Phase 6b prone tier A was implemented in iortcw branch codmod  CTRL binds to +prone (WBUTTON_EX"
type: decision
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 162, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, Phase 6b prone tier A was implemented in iortcw branch codmod: CTRL binds to +prone (WBUTTON_EXTRA7), C stays toggle crouch; prone state uses networked STAT_COD_FLAGS bits and STAT_COD_STANCE (not ET eFlags) because RTCW EF_TAGCONNECT collides with ET EF_PRONE.

