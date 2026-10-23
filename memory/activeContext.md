_Last updated: 2026-10-22_

## Current focus

**Loading-screen stutter (2026-10-23): architect plan done, Phase 0 (profiler `com_loadProfile` + `scripts/load-test.sh`) being implemented by coders, uncommitted.** Goal: >= 30 FPS (no present gap > 33 ms) on loading screens. Cause: the loading screen only redraws at ~20 `CG_LoadingString` calls (long blocks between them: world load, cubemaps, HD sound precache), and during `SV_SpawnServer` the renderer/UI are shut down so nothing can draw. Plan: Phase 0 measure; 1 rate-limited `CL_LoadingTick` (cvar `com_loadingFps`, code default 0, pinned 50 in codmod.cfg) at safe points + `ri.LoadingTick` in rend2 loops; 2 renderer "replay presenter" for the server phase / R_Init (touches rend2 present path: needs user verification); 3-5 optional (early R_Init, parallel GLSL, worker decode). Shared-GL-context loading thread rejected (Wayland/sdl2-compat). Baseline (user ran it): 11-14 gaps > 33 ms per map, 4.3-5.2 s load; first present only at ~1.1 s (server 0.5 s, R_Init 0.15, UI init 0.5), world load 1.6-2.0 s single block, ~0.9 s block after (models/sounds). Phase 1 (`CL_LoadingTick`, `com_loadingFps`, ticks in cgame register syscalls + rend2 `tr_bsp.c` loops, only in `CA_LOADING` after first `CG_UPDATESCREEN`) built/installed, uncommitted, awaiting the user's `scripts/load-test.sh --profile-level 2` re-run. Phase 1 result (user re-ran + played): presents 36 -> 115-128 per load, total time unchanged (5.1 s), user says loading feels much better; still ~35 gaps > 33 ms/map, p95 ~110 ms (first 0.9-1.16 s frozen; 35-160 ms single shader/image items in world load; 35-170 ms model/WAV items; EndRegistration 90-270 ms). Phase 2a (replay presenter `rend2/tr_loadscreen.c`, spinner, `CL_LoadingReplayTick`, hint column in profiler) built/installed, uncommitted: load-test shows 163-188 presents/load, p95 55-59 ms, 24-28 gaps > 33 ms (single HD texture/WAV decodes 33-120 ms, CM_LoadMap 116-190 ms, unmarked server stretch before r_init 145-204 ms, 160-380 ms after end_registration). Awaiting user in-game check of Phase 2a (HUD/menu/2D, level change, vid_restart, quit during load). Proposed Phase 2b: offload CPU-only heavy calls (image decode, WAV decode, CM_LoadMap, model parse) to a worker thread while main thread waits ticking the replay (sync hand-off, Com_Error from worker re-raised on main), cvar `com_loadingThread`; plus more marks.

**SMAA T2x (2026-10-22): done, user-verified in game, committed and pushed (engine 230ce365 + menu follow-up).** `r_aa 8`: jitter + reprojected history + RG16F velocity buffer (props, viewmodel, MDS limbs via `RB_SmaaMdsPrevPositions`). AA menu simplified: Off / SMAA 1x (`r_aa 4`, Ultra, default; saved 1-3 alias to 4) / SMAA T2x (Recommended, 8) / MSAA 2-4-8x (5-7). Bench 2560x1600: SMAA levels cost the same; T2x -5..7% (resolve 0.39 ms; `ssao_apply` 1.3 ms is the biggest pass). Next: decide T2x as default after more play, optional resolve optimisation. Docs: `docs/smaa.md`, `docs/smaa-motion-plan.md`.

**Guard eyes (2026-10-22): fixed, user-confirmed.** `h_blink` eyelids were not coplanar with the Loop-smoothed head; `mdc_smooth.py` now rebuilds skin-copy helpers from the skin subdivision (`copy_helper`, `LID_LIFT` 0.03). Leftover: `inge/head.mdc` still rides (4 lid tris triangulated differently).

**Highlights (2026-10-22): tonemap soft shoulder + bloom retune (threshold 0.8 / intensity 1.8) built/installed, uncommitted, awaiting user check** (sky/windows no longer flat white; `docs/post-effects.md`). Sun shadows `r_sunShadowStable 7` kept (user: no visible difference, fine).

**Stable sun shadows (2026-10-22): implemented, built/installed, uncommitted, awaiting user in-game check.** `r_sunShadowStable` bitmask (pinned 7 in `codmod.cfg`; 0 = vanilla): 1 sphere-fit texel-snapped cascades, 2 Castano bilinear PCF (no noise), 4 cascade-edge blend. Bench 266 -> 253 fps. Details and open checks in `docs/sun-shadows.md`. User to strafe/turn in the escape2 courtyard, A/B with `r_sunShadowStable 0`; if bad, bisect bits.

**Parallax (2026-10-22): done and committed, perf phases 1-2 in; user approved performance.** All 33 SP maps baked (`run/codmod/codmod_height.pk3`, 293 textures, 72 flattened). Menu: Normal Maps Off/On + Parallax Off/On/On+Self-Shadows (`docs/parallax.md`). Bench 1920x1200: normals-only 261 fps, parallax relief+shadows 258 (was 196). Live cvars `r_parallaxStepDensity` 1, `r_parallaxMarchLod` 0, `r_parallaxShadowFade` 0; latched `r_parallaxMinDepth` 0.15; `r_parallaxMapShadows` is a bitmask. **Mouse-motion perf drop (2026-10-22): fixed, user-confirmed, committed** (VAO cache static store + `glMultiDrawElements`; `docs/performance.md` "View-motion smoke test"). Smoke test: `scripts/spin-test.sh`. Benchmarks always run off-screen (`bench.sh` is headless by default).

**Bevel corners (2026-10-22): connected textures + corner lighting accepted by user as good enough for now; uncommitted (tool in `tools/world-bevel-jl`, `scripts/shot-at.sh`, `scripts/seam-metric.py`, engine `viewpos`/`setviewpos` pitch + `uiclick`). Future ideas listed in `progress.md`.**

**SMAA motion (2026-10-21): phases 1 (`r_smaaPredication`) and 1b (`r_specularAA`) done and committed, user says modest gain; flashlight shadow map 2048 default + menu row committed. User will decide when to start SMAA T2x (plan `docs/smaa-motion-plan.md`, phase 3a camera-only first). Sun shadows swim on camera motion (`lightViewIndependentOfCameraView = qfalse` in `R_RenderSunShadowMaps`, no texel snapping) and PCF uses screen-fixed random rotation; candidate follow-up.**

**One-time flashlight tip (2026-10-21): user-confirmed in-game (shows once), committed and pushed.** Flashlight ON/OFF print removed; `CG_CodUpdateTips` (cg_cod.c) center-prints "Toggle Flashlight with <key>" (de/es via template in strings.txt) once after 4 s of control in a level; archived cvar `cod_tipFlashlightShown` (cg_main.c) marks it shown (also set on first manual toggle). New cgame trap `CG_KEY_KEYNUMTOSTRING` (engine change, cl_cgame.c).

**Knight statue pink specular (2026-10-21): user confirmed fixed in-game; committed and pushed (5ce0539). Both derived packs now auto-built (incremental) by `scripts/build-derived-packs.sh`, called from setup.sh/install.sh.** Cause: knight_anim.mdc maps cap/shoulder faces (8 surfaces) into an empty black diamond of knt.tga (original asset quirk); spec_bake.py tint `rgb/luma` amplified black noise to purple with 22% base F0. Fix: spec-bake fades tint/F0/gloss on near-black texels; new private tool `tools/asset-fixes/fix_assets.py` -> `run/codmod/codmod_zfix.pk3` paints dull steel into the diamond; spec-bake reads zfix first. Run order: hd-textures, asset-fixes, spec-bake.

**Tactical AI overhaul (2026-10-18): Phase 1 user-confirmed in-game ("working great"), uncommitted; Phase 2 (squads: tokens, bounding advance, flanking, suppression, barks; `ai_cast_cod_squad.c`, cvars `cod_aiSquad` etc.) user-confirmed in-game. Fullscreen-switch fix (soft vid_restart rebuilds at new size, `sdl_glimp.c`/`sdl_input.c`) user-confirmed. All uncommitted. Phase 2b "push for an angle" (no clean shot for `cod_aiNoShotTime` -> a pusher goes to a COVER_ANGLE spot with a body shot, others suppress; fallbacks grenade / advance; `cod_aiPush`) user-confirmed in-game. Phases 1-2b + fullscreen fix committed and pushed 2026-10-18 (engine 18458e2c, 8102f198). Phase 3 (threat reactions: proactive grenades with squad cooldown, grenade dodge, near-miss suppression lowering accuracy, low-health / broken-morale retreat, opportunism when the player is weak; cvars `cod_aiGrenadeHold` etc.) user-confirmed and committed 2026-10-18 (engine a51b3dd0). Phase 4 (search/hunt, `ai_cast_cod_hunt.c`, cvars `cod_aiHunt` etc.) user-confirmed and committed 2026-10-18. Phase 5 (movement/aim polish, `ai_cast_cod_polish.c`, master `cod_aiPolish`, BG_COD_MAX_CVARS now 288) user-confirmed and committed 2026-10-20. Phase 6 (difficulty scaling `cod_aiSkillScale`, perf counters, all-maps load test, `docs/ai-tactics.md`) user-confirmed and committed 2026-10-20: tactical AI overhaul complete (all 6 phases). Player kick reverted to vanilla 15 dmg (committed). Quit-during-map-load crash fix (`SV_FinalMessage` skips loopback, sv_init.c) committed 2026-10-20. Gotcha: a fresh empty fs_homepath crashes at start (signal 11) and leaves iowolfsp.pid, so the next launch waits on the safe-options popup.** Plan: `docs/ai-overhaul-plan.md` (6 phases, phase-gated). Phase 1 = game-side cover finder (`ai_cast_cod_cover.c`) + combat state machine OPEN/MOVE/HIDE/PEEK (`ai_cast_cod.c`, `AIFunc_CodCombat`), routed from vanilla Battle/BattleTakeCover/BattleChase. Toggle MODS > GAMEPLAY "Tactical Enemies" (`cod_optTactics`); internal master `cod_aiTactics`; debug `cod_aiDebug 1` (console `[ai]` lines) / `2` (rail-trail cover markers). Tuning cvars in `codmod_tuning.cfg`. User to check escape1/escape2: soldiers take cover, crouch behind low walls, peek corners; A/B with `cod_optTactics 0`; save/load mid-fight. Next after OK: Phase 2 (squads, flanking, suppression).

**Gameplay options (2026-10-18): built/installed, uncommitted (both repos), awaiting user in-game check.** MODS > GAMEPLAY: 11 on/off toggles `cod_opt*` (Movement, Slide, Prone, Aim Down Sights, Recoil, Weapon Handling, Health Regeneration, CoD Stamina, More Ammo, Hit Markers, Fast Enemies). Archived, code default 0, `seta 1` in `codmod_defaults.cfg`; `BG_CodApplyOptions()` (bg_cod.c) clears the feature flags per group. Menu `gameplay.menu` (codmod layer, delta exported). `BG_COD_MAX_CVARS` raised 192 -> 256. Docs: `docs/gameplay-options.md`. Smoke: cvars register, no menu parse errors; not yet clicked through in-game (toggle each, check Slide needs Movement, regen/enemy options apply on map load).

**opengl1 removal (2026-10-18): done, user-checked, merged (PR #3).** SP only (MP untouched, user choice): `SP/code/renderer/` deleted, shared headers in `SP/code/renderercommon/`, rend2 the only renderer, `cl_renderer` has no renderer choice (`cl_renderer` removed; always rend2). **Capability/config split: merged (PR #2).** Plan: `docs/capability-split-plan.md`. Engine defaults vanilla (rend2 default renderer), mod hooks `<fs_game>_defaults.cfg`/`<fs_game>.cfg` in `Com_ExecuteCfg`, `execmodcfg` for menu Reset; mod files `codmod_defaults.cfg` (user-facing), `codmod.cfg` (pinned, execs `codmod_tuning.cfg`); `run.sh` only adds `fs_game`. Verified: shots identical to `presplit` (shot02 flaky), fresh-home codmod and `--vanilla` cvar dumps correct. Menu two-layer split done; the engine layer + builder now live in the fork (`iortcw/SP/menus/`, `menudelta.py`), and `iortcw/SP/run-sp.sh` runs the fork standalone as plain RTCW with its menus. Fixed RTCW's MODS-panel overlay (setup.menu Esc/BACK) in the engine layer (engine pk3 ships the fork's `menudef.h`; vanilla and codmod launch with no menu errors), docs done. Binds: user chose defaults only (no binds in `codmod.cfg`; all in `codmod_binds.cfg`, saved rebinds persist, Defaults resets). Phase 2 (remove opengl1 entirely) only after user OK.

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

**Weapon normals (2026-10-22):** pistol A/B approved by the user (small positive); all 27 weapon skins baked into `run/codmod/codmod_height_weapons.pk3` (normals only; hands/arms and effect skins excluded). **Awaiting the user's in-game look** at the other weapons; remove the pk3 to revert. Not committed (pk3 git-ignored; tool + docs changed).
