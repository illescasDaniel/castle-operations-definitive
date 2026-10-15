_Last updated: 2026-10-15_

## Current focus

**Lean + aim bug (2026-10-15): implemented, builds clean (engine `3e63880a`), step 4 (ADS viewmodel lean fade) added after the user saw sights off; awaiting re-check.** Shots landed ~10 u above the crosshair while leaning (camera offset used a roll-tilted right vector, server `AddLean` did not). Now both use `BG_CodLeanOffset`. Checklist in `docs/lean-aim-fix.md`; step 4 (ADS viewmodel) only if sights still look off.

**Strafe + counter-aim jitter fix (2026-10-14): done, user-verified, engine `76e18436`.** Both camera cvars are internal (cl_viewSmooth code default, cg_subMsecLerp pinned in codmod.cfg). Gotchas: a scripted run ended by SIGINT hangs in GLSL shutdown; scripted `+quit` during map load segfaults.

**Lossless GPU pass savings (2026-10-14): done, user confirmed, committed and pushed** (engine 01452ea2).
Bench 247 -> 303 FPS (GPU 4.07 -> 3.21 ms/frame); details and per-pass profile in docs/performance.md
("GPU pass profiling").

Before that: GPU utilisation fix done, committed and pushed (engine 0b6f57fc).

Previously:

Phase 7 extras, in order: **E4 ADS sway/breath** (cgame-only, small), then **E5 CoD-style recoil model** (medium).
Specs in `docs/phase-7-extras.md`; ADS context in `docs/phase-3-ads.md`. Phase gating applies: build, report, stop for
the user's in-game confirmation before the next one.

## State

- Both repos clean (outer `main`, `iortcw/` `main`) as of 2026-10-14.
- User confirmed working 2026-10-13: menu FPS limit, Skip Intro + cutscene letterbox, HD cutscene videos (`nlm1+span`),
  SSAO/GTAO + ambient-only AO (`r_ao`), frame pacer + `r_vsync` modes, HD audio pack.
- Original phases 1-6b (tier A) all shipped and confirmed. Optional leftovers: 6b tier B (third-person prone anims),
  E13 AI sprint, E11 packaging, localization L0-L2, custom menu title art.

## Blockers

None.

## Known gaps

- Frame pacer / vsync: Windows untested; vsync modes 1-3 not validated on this Wayland box.
- Flashlight: metallic/baked-light items still reflect little.

## Next steps

1. E4: idle ADS sway scaled by movement, `cod_*` cvars (default in `bg_cod.c`, reset in `codmod_binds.cfg`).
2. E5: per-weapon pitch/yaw kick with recovery, reduced in ADS (`CG_KickAngles`, `cg_view.c`).

## Historical notes

Earlier session detail (release prep, benchmark, perf investigation, SMAA, fork switch, HRTF) is recorded in
`progress.md`, `archive.md`, `decisions.md` and `docs/`.
