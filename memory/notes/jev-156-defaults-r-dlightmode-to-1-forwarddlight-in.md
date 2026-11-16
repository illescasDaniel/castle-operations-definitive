---
name: jev-156-defaults-r-dlightmode-to-1-forwarddlight-in
description: "On 2026-10-09, rtcw-cod defaults r_dlightMode to 1 (ForwardDlight) in codmod.cfg and scripts/run.sh because fl"
type: decision
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 156, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, rtcw-cod defaults r_dlightMode to 1 (ForwardDlight) in codmod.cfg and scripts/run.sh because flashlight spot cones need N·L forward lighting; r_dlightMode is CVAR_LATCH so run.sh +sets it before InitRef.

