---
name: jev-163-prone-on-ctrl-failed-because-cl-cmdbuttons
description: On 2026-10-09, prone on CTRL failed because CL_CmdButtons in cl_input.c packed wbuttons with a loop i < 7, so
type: incident
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 163, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, prone on CTRL failed because CL_CmdButtons in cl_input.c packed wbuttons with a loop i < 7, so KB_WBUTTONS7 / WBUTTON_EXTRA7 (bit 128) never reached usercmd_t; fix is i < 8. ADS on wbutton6 was unaffected.

