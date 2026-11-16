---
name: jev-260-decision-the-player-kick-went-back-to
description: "On 2026-10-20, rtcw-cod decision  the player kick went back to vanilla RTCW strength (cod_kickDamage 15 in mod"
type: decision
date: 2026-10-20
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 260, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-20, rtcw-cod decision: the player kick went back to vanilla RTCW strength (cod_kickDamage 15 in mod/codmod/codmod_tuning.cfg, was 50 since 2026-10-12) because the user found it too powerful. Damage was the only kick change the mod ever made (Cmd_WolfKick_f in g_cmds.c); the AI soldiers' kick (cod_aiKick*) is separate.

