---
name: jev-172-iortcw-under-game-run-sh-mangohud-gamemode
description: On 2026-10-09, ioRTCW under game_run.sh (MangoHud + gamemode, SDL Wayland) SIGSEGV'd on fullscreen Apply becau
type: incident
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 172, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, ioRTCW under game_run.sh (MangoHud + gamemode, SDL Wayland) SIGSEGV'd on fullscreen Apply because vid_restart destroyed/recreated the GL context; the fix is IN_ToggleFullscreenInPlace and GLimp_EndFrame using SDL_SetWindowFullscreen (FULLSCREEN_DESKTOP on Wayland) for fullscreen-only changes and never falling back to vid_restart, with Cvar_LatchedPending/Cvar_VariableLatchedInteger peeking latches because Cvar_Get would apply them.

