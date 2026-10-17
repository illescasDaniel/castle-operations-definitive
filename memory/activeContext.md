_Last updated: 2026-10-16_

## Current focus

**Flashlight not lighting objects (2026-10-17): fixed, built/installed, uncommitted, awaiting user check.** Cause: `ForwardDlight` (tr_shade.c) did not enable the specular map (`u_EnableTextures.z`), so with specular on by default `diffuse *= 1 - specular` zeroed albedo on every `_s`-mapped surface (wood, metal, doors, chains); walls fine. Also fixed brush-model dlight culling in tr_world.c (`r_dlightModelSpace`). Details in `docs/flashlight-shadows.md`. Metal bands glare strongly (`r_deluxeSpecular 3`); tune if the user dislikes it.

**30 FPS stutter + camera-following specular hotspot + bloom/grade on by default (2026-10-17): built/installed, uncommitted, awaiting user in-game check.** 30 FPS: `cg.predictLagMs` was zeroed above 33 ms, so at 30 FPS (33/34 ms) the view extrapolation toggled every frame; now clamped (cg_predict.c), view-clock reset scales with frame time (cl_cgame.c). Hotspot: baked vertex light dir fell back to the surface normal, so N~L~E gave a highlight wherever the camera looked; light-dir length now encodes directionality (tr_light.c `R_LightDirForPoint`, `r_codSpecDirectional` default 1, map reload to A/B; lightall_fp.glsl). Bloom levels 1/1.6/2.4, default Medium; grade default on.

**Bloom + colour grade (2026-10-17): committed, verified in-game by user, ON by default (`r_bloom` 2 = Medium, `r_grade` 1; levels x1/1.6/2.4; old saved wolfconfig values are kept).** Smoke-tested with `shots.sh`; GRAPHICS menu rows added (Bloom Off/Low/Med/High, Color Grade; deltas exported, reset in `codmod_binds.cfg`). Bloom rebuilt as mip chain (2026-10-17) after user said the first looked like a floating blob: tight glow + halo. 2026-10-17 fix: glows were drawn upside down (FBO_Blit flips Y with srcBox + NULL dstBox; the "misplaced lights"), chain now normalised (weight 0.8), defaults intensity 2.5 / threshold 0.6, grade brightness 1.25. Cost: bloom ~0.4 ms GPU (277 -> 230 FPS on bench), grade ~0.15 ms GPU. Tuning cvars pinned in codmod.cfg (wolfconfig had stale values). User to check the menu rows in-game. Maybe HDR bloom later. Other ideas surveyed: sun shafts exist (`r_drawSunRays`), DoF/bokeh exists in rend2 (`blurFactor`), motion blur / film grain / lens dirt not yet.

**Specular perf fix (2026-10-17): committed and pushed; user approved. Specular is now ON by default (`r_codSpecular` default 1, row moved to GRAPHICS > ADVANCED; guarded `+set` in run.sh). A saved `r_codSpecular 0` in an existing wolfconfig still wins.** Spec-on FPS 141 -> 267 (spec off 274): cubemap index split draw batches (3500/frame); fixed via cubemap gating in `R_AddDrawSurf`, radix pass, ai_marker clustering (`r_cubemapMergeDist`), `r_cubemapSpecOnly`, shader uniform branches. Details in `docs/performance.md` ("Specular cost"). User to check metal/armor/glass reflections still look right (probes now only on spec-mapped shaders, 33 instead of 164).

**Specular highlights (2026-10-16): user confirmed weapons/metal look great; rolled out to all game materials, awaiting in-game check.** `tools/spec-bake` classifies ~490 textures by path regex (gunmetal/armor/metal/wood/marble/stone/glass/ceramic) into private `run/codmod/codmod_spec.pk3` (148 MB, git-ignored; rerun after setup). Defaults pinned: `r_deluxeSpecular 3` + `r_cubeMapping 1` (codmod.cfg + run.sh +set). Engine fix (decouple deluxe specular from cubemaps, `tr_glsl.c`) uncommitted in `iortcw/`. Open: perf cost of cubemaps/pack, tune per-class gloss, regenerate packaging docs.

**Glasses / letterbox / AO fog (2026-10-16): done, committed.** Glasses cause: AO blit left viewport full-screen (fixed with `SetViewportAndScissor()`). Cutscene letterbox bars removed. AO now fades with global fog and the fog-volume pass is drawn after the AO multiply. User confirmed fog fix; 4:3 briefing in-game check still pending.

**Cutscene speed + 4:3 briefing (2026-10-16):** built/installed, engine changes uncommitted in `iortcw/`. User to check cutscene1 Jack walk/glasses and briefing screens; if glasses still off, A/B screenshot rend2 vs opengl1 (see plan file).

**Cutscene AO re-enabled (2026-10-16):** `r_cutsceneFx` default 31 (AO bit on); user confirmed. **AO through translucents (2026-10-16):** multiply AO after opaques, before blends (curtains no longer get wall AO overlay). Prior: cutscene/exposure pushed (engine `61c9cbf6`, outer `2bf6075`). User: verify curtains/glass with AO on.

**Soft vid_restart for MangoHud (2026-10-16): implemented, smoke-verified under mangohud Wayland.** Mode Apply keeps GL context (`re.Shutdown(qfalse)` + `GLimp_SetModeInPlace`); hard path only for context-attribute latches. Engine changes in `iortcw/` uncommitted until user asks. GRAPHICS Video Mode Apply under `game_run.sh` should no longer SIGSEGV.

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

1. In-game: New Game → escape1 intro with `r_cutsceneFx 0` (baked only); re-enable bits to find culprit; outdoor sun after cam.
2. Commit engine cutscene-sun + soft-vid_restart + outer submodule pointer when user asks.
3. E4/E5 leftovers only if user wants that thread again.

## Historical notes

Earlier session detail (release prep, benchmark, perf investigation, SMAA, fork switch, HRTF) is recorded in
`progress.md`, `archive.md`, `decisions.md` and `docs/`.

## Subtitles (2026-10-15)
Committed and pushed 2026-10-15 (user verified in-game, cutscenes too). `tools/subtitles/` (faster-whisper large-v3: transcribe.py, pack.py, review_page.py), `cg_subtitles.c`, `cod_subtitles` toggle (Game menu + pause Game), pack `run/codmod/codmod_subtitles.pk3` (620 lines, private). Docs: `docs/subtitles.md`. Awaiting user: in-game check (timing, wrapping, cutscene visibility, toggle) and listen to `tools/subtitles/build/review/index.html` (147 CHECK/RECOVERED lines). Known gap: ~250 dropped clips are mostly SFX; a few real barks (e.g. "Schnell", "Danke") got no text.

## Specular + Display tab (2026-10-17)
Committed and pushed (user tested). `tools/spec-bake/` bakes `_s` maps per material into `run/codmod/codmod_spec.pk3` (git-ignored). Engine: `r_deluxeSpecular 3` + `r_cubeMapping 1` pinned; BSP-baked vertex-lit props now take specular (`tr_shader.c` collapse); `r_codSpecular` (latched, default now 1 since 2026-10-17, ADVANCED tab) gates spec maps, light-grid specular and cubemaps. Options menu now DISPLAY / GRAPHICS / ADVANCED; `r_displayMode` (windowed/borderless/fullscreen) is a view over `r_fullscreen`+`r_noborder` (`CL_ApplyDisplayMode`). Open: specular perf cost still unmeasured; enable by default once cheap.
