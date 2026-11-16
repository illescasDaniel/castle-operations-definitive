---
name: jev-142-save-load-sigsegv-in-clientthink-real-g
description: On 2026-10-09, rtcw-cod save-load SIGSEGV in ClientThink_real G_SetOrigin was caused by gclient cameraPortal b
type: incident
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 142, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, rtcw-cod save-load SIGSEGV in ClientThink_real G_SetOrigin was caused by gclient cameraPortal being a raw pointer not listed in gclientFields, so legacy saves restored garbage addresses; fix ignores cameraPortal and persistantPowerup on load and nulls them after ReadClient.

