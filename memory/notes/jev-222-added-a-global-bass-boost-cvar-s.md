---
name: jev-222-added-a-global-bass-boost-cvar-s
description: "On 2026-10-12, rtcw-cod added a global bass boost (cvar s_alBass, dB, low-shelf biquad at 200 Hz) in iortcw/SP"
type: decision
date: 2026-10-12
status: superseded
supersedes: 
superseded_by: jev-223-tried-a-global-bass-boost-s-albass
source:
---

Historical jevmem entry 222, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-12, rtcw-cod added a global bass boost (cvar s_alBass, dB, low-shelf biquad at 200 Hz) in iortcw/SP snd_openal.c, applied to PCM right before qalBufferData (SFX, music, raw audio). Chosen over OpenAL EFX because EFX aux-slot output is not HRTF-spatialized and the dry path would have to be muted, which breaks the 3D audio. Changing the cvar kills non-stream sources and unloads cached SFX buffers so they reload filtered. Gotcha: codmod_menus.pk3 is a prebuilt tracked binary, so menu edits need it repacked (no zip binary on this box; use python zipfile).

