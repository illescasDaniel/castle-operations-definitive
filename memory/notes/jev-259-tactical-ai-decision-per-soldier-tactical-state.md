---
name: jev-259-tactical-ai-decision-per-soldier-tactical-state
description: "2026-10-18 RTCW codmod tactical AI decision  per-soldier tactical state lives in static arrays (codAI   in ai_"
type: gotcha
date: 2026-10-18
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 259, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-18 RTCW codmod tactical AI decision: per-soldier tactical state lives in static arrays (codAI[] in ai_cast_cod.c), never in cast_state_t, because cast_state_t is saved to savegames as a raw struct. Every new AIFunc_* (e.g. AIFunc_CodCombat, AIFunc_CodCombatStart) must be listed in g_funcs.h and g_func_decs.h, or saving fails with "WriteField1: unknown function". Cover is found game-side with hull traces because AAS_NearestHideArea only returns fully hidden spots the AI cannot shoot from.

