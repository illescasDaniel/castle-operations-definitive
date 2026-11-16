---
name: jev-171-iortcw-on-wayland-can-emit-sdl-windowevent
description: "On 2026-10-09, ioRTCW on Wayland can emit SDL_WINDOWEVENT_RESIZED with only ±1 or ±2 pixel deltas versus the c"
type: incident
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 171, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, ioRTCW on Wayland can emit SDL_WINDOWEVENT_RESIZED with only ±1 or ±2 pixel deltas versus the current vidWidth/vidHeight; treating those as real resizes set r_mode -1 with odd sizes like 1921x1201 and a delayed vid_restart that SIGSEGV'd under MangoHud, so sdl_input.c now ignores resize deltas of 2 pixels or less.

