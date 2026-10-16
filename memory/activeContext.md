_Last updated: 2026-10-16_

## Current focus

**Video Mode popup (2026-10-16): committed/pushed** (engine `7f342afe`, outer `80de7c7`). Also fixed `load.menu` fadebox missing `}` (delete-confirm parse error). Quit cleanly to pick up menus pk3.

**Menu cursor (2026-10-16): done, user verified in-game, engine `2d81a83e`.** New dagger art `ui/assets/codmod_cursor.tga` (in `codmod_pad.pk3`, source PNG next to it); art tip is the top-left pixel = hotspot; drawn square from `yscale` (size 24 in `ui_main.c`).

**Multi-language (2026-10-16): done, user verified in-game.** Text packs de/es (`mod/codmod/lang/`), selector on main menu, `cod_textLang`/`cod_audioLang`/`cod_subtitleScale` (edit field). Docs: `docs/languages.md`. Next: subtitle font/outline style.

**Lean + aim bug (2026-10-15): done, user confirmed.** Shared `BG_CodLeanOffset` (camera + server `AddLean`) plus viewmodel lean fade in ADS. Use `scripts/build.sh --install` (build alone leaves stale modules in `run/`).

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

- Both repos clean (outer `main`, `iortcw/` `main`) as of 2026-10-14. `iortcw/` is now a submodule (2026-10-15): bump the pointer after engine commits.
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

1. In-game: GRAPHICS → Video Mode → popup scrolls/selects; double-click or Back closes; Apply still applies `r_mode`.
2. E4/E5 leftovers only if user wants that thread again.

## Historical notes

Earlier session detail (release prep, benchmark, perf investigation, SMAA, fork switch, HRTF) is recorded in
`progress.md`, `archive.md`, `decisions.md` and `docs/`.

## Subtitles (2026-10-15)
Committed and pushed 2026-10-15 (user verified in-game, cutscenes too). `tools/subtitles/` (faster-whisper large-v3: transcribe.py, pack.py, review_page.py), `cg_subtitles.c`, `cod_subtitles` toggle (Game menu + pause Game), pack `run/codmod/codmod_subtitles.pk3` (620 lines, private). Docs: `docs/subtitles.md`. Awaiting user: in-game check (timing, wrapping, cutscene visibility, toggle) and listen to `tools/subtitles/build/review/index.html` (147 CHECK/RECOVERED lines). Known gap: ~250 dropped clips are mostly SFX; a few real barks (e.g. "Schnell", "Danke") got no text.
