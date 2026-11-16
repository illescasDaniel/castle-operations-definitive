---
name: jev-224-cut-the-graphics-options-menu-to-a
description: On 2026-10-12, rtcw-cod cut the GRAPHICS options menu to a single page (Video Mode, Fullscreen, VSync, FPS lim
type: decision
date: 2026-10-12
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 224, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-12, rtcw-cod cut the GRAPHICS options menu to a single page (Video Mode, Fullscreen, VSync, FPS limit, Anti-Aliasing, Brightness, Driver Info, Benchmark) because benchmarks showed most rows had ~0 effect or were re-pinned by codmod.cfg/run.sh every launch (SSAO, shadow size, AF), so menu changes never persisted. codmod_menus.pk3 has no build script; it is repacked by rewriting the zip entries from mod/codmod/ui (no `zip` binary installed, use python zipfile).

