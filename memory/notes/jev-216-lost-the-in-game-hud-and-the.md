---
name: jev-216-lost-the-in-game-hud-and-the
description: "On 2026-10-11, rtcw-cod lost the in-game HUD and the visible pause menu because a rend2 perf edit made RB_Post"
type: incident
date: 2026-10-11
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 216, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-11, rtcw-cod lost the in-game HUD and the visible pause menu because a rend2 perf edit made RB_PostProcess leave the final frame in tr.msaaResolveFbo and RB_SwapBuffers present that FBO directly. With MSAA on (r_ext_framebuffer_multisample 2, the codmod default), all 2D drawn into tr.renderFbo after post-process was discarded. Earlier guesses about the cutscene camera or orphan fullscreen UI were wrong. Fix: shelve that edit; the 2D pass must always reach the backbuffer.

