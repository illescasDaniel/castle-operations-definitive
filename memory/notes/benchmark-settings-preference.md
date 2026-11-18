---
name: benchmark-settings-preference
description: Benchmarks always use r_frameWarp 0, native resolution and r_renderScale 1.0 unless the user says otherwise
type: preference
date: 2026-11-18
status: current
supersedes:
superseded_by:
source: user
---

Never benchmark with frame warp on (`r_frameWarp 0`) unless the user explicitly asks: frame warp inflates fps. Render at the user's native resolution (bench default 1920x1200) with internal resolution `r_renderScale 1.0`, not the in-game default 0.7. Pass `r_frameWarp 0` and `r_renderScale 1` in every `benchmark`/`profile` call (common `cvars`), and check the profile header or cfg line says so. Incident: the 2026-11-18 perf campaign first ran with frame warp 2 and renderScale 0.7 (the `profile`/A/B defaults), so those numbers were discarded and redone.
