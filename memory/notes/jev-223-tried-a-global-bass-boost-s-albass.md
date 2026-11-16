---
name: jev-223-tried-a-global-bass-boost-s-albass
description: On 2026-10-12, rtcw-cod tried a global bass boost (s_alBass  low-shelf biquad at 200 Hz applied to PCM before
type: decision
date: 2026-10-12
status: current
supersedes: jev-222-added-a-global-bass-boost-cvar-s
superseded_by: 
source:
---

Historical jevmem entry 223, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-12, rtcw-cod tried a global bass boost (s_alBass: low-shelf biquad at 200 Hz applied to PCM before qalBufferData in iortcw/SP snd_openal.c, plus a sound-menu row). The user was not convinced and heard crackling/popping; they concluded the "not deep enough" feeling is probably a headphones/DAC/speakers matter, not game-related, and asked to discard it, so everything was reverted (engine, menus pk3, docs). Do not re-propose engine EQ for this; if revisited, suggest an OS/system-level EQ (e.g. EasyEffects/PipeWire) or offline baking into files. Design notes if ever retried: OpenAL EFX equalizer rejected because aux-slot output is not HRTF-spatialized; filter-at-upload needs a constant gain per stream (no per-chunk peak scaling), loop-safe warm-up, and state reset on track change. codmod_menus.pk3 is a tracked prebuilt binary; repack with python zipfile (no zip binary).

