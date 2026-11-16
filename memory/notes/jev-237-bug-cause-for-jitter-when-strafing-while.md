---
name: jev-237-bug-cause-for-jitter-when-strafing-while
description: "On 2026-10-14, rtcw-cod bug cause for jitter when strafing while counter-aiming at a fixed point  in ioRTCW CL"
type: incident
date: 2026-10-14
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 237, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-14, rtcw-cod bug cause for jitter when strafing while counter-aiming at a fixed point: in ioRTCW CL_Frame, CL_SendCmd runs before CL_SetCGameTime, so the predicted player origin is at the previous frame's cl.serverTime (one 4/5 ms frame behind mouse look), and CL_AdjustTimeDelta nudges cl.serverTime +1/-2 ms per snapshot. Fixed with an engine view clock (CL_UpdateViewClock in cl_cgame.c, eased 4%/frame toward the game clock, driven by com_frameClockUs) and a cgame view extrapolation by predictLagMs plus the view-clock offset. Gotchas: a scripted run ended by SIGINT hangs in GLSL shutdown, and +quit during map load segfaults.

