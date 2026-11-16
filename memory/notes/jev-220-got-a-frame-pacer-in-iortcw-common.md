---
name: jev-220-got-a-frame-pacer-in-iortcw-common
description: "On 2026-10-12, rtcw-cod got a frame pacer in ioRTCW (common.c Com_FrameWaitTop/Com_PresentWait/Com_PresentDone"
type: incident
date: 2026-10-12
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 220, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-12, rtcw-cod got a frame pacer in ioRTCW (common.c Com_FrameWaitTop/Com_PresentWait/Com_PresentDone, ri.PresentWait/PresentDone hooks around SDL_GL_SwapWindow, Sys_WaitUntil sleep+spin) and r_vsync 0-4 (Off/On/Adaptive/Triple/Low latency, live-applied in sdl_glimp.c). Gotcha: codmod.cfg is exec'd every launch so it overwrites menu choices; user-facing display cvars (com_maxfps, com_maxfpsMode, r_vsync) therefore have first-launch defaults in codmod_binds.cfg instead. On this Wayland+NVIDIA 240 Hz box swap interval 1 did not throttle (~350 fps in bench), so vsync modes 1-3 were unvalidated and r_vsync 4 falls back to a refresh-rate cap when swap intervals do not look like a vblank. Predictive-mode lead must be clamped below the period or spikes disable pacing.

