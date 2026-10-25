# Progress

Open items first. Finished work moves to `archive.md`. Phase details live in `docs/plan.md` (section 7 mirrors this list).

## RTCW remaster (`codmod`) — CoD4 feel + HD presentation

### Done
- [x] **rtcw-mcp server (2026-10-23, uncommitted):** `tools/rtcw-mcp/` (MCP stdio, `.venv`, README): `screenshot`, `texture_coverage` (`normalcov`), `console_log`, `load_times`, `benchmark` (+ `--gpuprof`), `compare_shots`, `build`; lock file + refuses when a game runs; verified headless on trainyard (`town_c22a1burn` = parallax). Not registered; user decides (`claude mcp add` in its README). `shots-diff.py` now also globs `spot*.tga`; `bench.sh --gpuprof` prints/saves the GPU pass table; `docs/testing.md` has the `normalcov`/intro-skip notes.
- [x] **Mouse-motion perf drop fixed (2026-10-22, user-confirmed):** rend2 VAO cache re-uploaded ~50 MB/frame on view change; now static vertex+index store with `glMultiDrawElements` (turning GPU 6.7-12.6 -> 3.4-3.6 ms). `scripts/spin-test.sh` smoke test added; `bench.sh` now always runs off-screen (headless gamescope). `docs/performance.md` "View-motion smoke test".
- [x] **Knight statue pink specular + black pauldron (2026-10-21, user-confirmed, committed 5ce0539; auto-built via build-derived-packs.sh):** spec-bake near-black tint/F0 fade; new `tools/asset-fixes` -> private `codmod_zfix.pk3` (knt.tga dump-diamond painted dull steel).
- [x] **Bloom + colour grade (2026-10-17, committed, verified in-game by user):** `RB_PostFx`, cvars `r_bloom*`/`r_grade*` on by default (bloom Medium, grade on), `docs/post-effects.md`. GRAPHICS menu rows done; FPS cost measured (docs/post-effects.md).
- [x] **Specular perf fix (2026-10-17, uncommitted, awaiting in-game check):** 141 -> 267 FPS on bench; cubemap batch splitting removed/clustered (`docs/performance.md` "Specular cost")
- [x] **Specular highlights (2026-10-16, user-approved direction; full rollout awaiting in-game check):** `tools/spec-bake` bakes `_s` maps for ~76 hand-tagged textures into private `codmod_spec.pk3`. Finding: engine `r_deluxeSpecular 0.1` hides them; with `1.0` armor/weapon metal shows. Cubemaps (`r_cubeMapping 1`) render from ai_marker/misc_cubemap at runtime, effect mild. Waiting for user in-game A/B before touching defaults.
- [x] **Cutscene AI speed + 4:3 briefing (2026-10-16, uncommitted, awaiting user check):** `AICast_CodApplySpeedMode` now skips scripted events (Jack/Director walked too fast in cutscene1, civilians got CoD speeds); briefing/pregame menus forced 4:3 on widescreen via `ui_force43` in `UI_AdjustFrom640` + blurred dimmed levelshot backdrop (`UI_DrawBriefingBackdrop`, ui_main.c). Jack's glasses misplacement: textures/shader ruled out, re-check after speed fix (plan: `~/.claude/plans/i-m-comparing-our-game-mod-temporal-hollerith.md`).
- [x] Public release prep: README/LICENSE/credits, setup.sh applies patches, patches re-exported (2026-10-12; see activeContext for open items)
- [x] Root `README.md` (what / install / run) (2026-10-08)
- [x] Planning docs and all design decisions D1-D10 (2026-10-08)
- [x] Memory bank and jevmem set up (2026-10-08)
- [x] Phase 1: setup and baseline build (confirmed in-game 2026-10-08)
- [x] Phase 2: movement (confirmed in-game 2026-10-08)
- [x] Phase 3 core: ADS state, FOV, move/spread, Luger iron sights + ADS center-dot (confirmed in-game 2026-10-08)
- [x] Phase 4: gait / FP movement presentation + sprint gun raise (confirmed in-game 2026-10-08)
- [x] Phase 5: movement weight + fire responsiveness (confirmed in-game 2026-10-08)
- [x] Phase 5.5: quick knife on V + snappy switch/return (confirmed in-game 2026-10-08)

### Open
- [ ] Frame warp (async reprojection): Stage 0 `r_warpDebug` built 2026-10-24, awaiting user in-game check; then chunks 2-4 (Stage 1), Stage 2 preemption (see activeContext)
- [ ] **Character smoothing experiment (2026-10-21, uncommitted; user approved the v2 look on 2026-10-21, commit when asked):** `tools/model-smooth`
  (numpy, no Blender) does one Loop subdivision on all 32 MDS bodies with exact skin weights (linear stencil commutes
  with skinning), pinned boundaries, crease angle, rebuilt LOD collapse map -> private `run/codmod/codmod_smooth.pk3`
  (installed, 90° crease). Verified: byte-identical round trip, no cracks, LOD ok, loads in game. In-game A/B (BJ third
  person, escape1): rounder shoulders/back. v1 sheared the texture (flag patch is painted in the sleeve UV island,
  not a decal mesh); v2 (installed) keeps only the normal part of the Loop displacement, stored as a bone-local offset
  correction, plus decal-shell displacement transfer: flag/chevron/patch now match the original, texture-distortion
  metric halved. Bench demo shows no MDS characters (avg FPS same; 1% low 157 -> 140, inconclusive). Heads (MDC)
  untouched. Next: user verdict in-game; then commit tool, README, docs/plan.md line.
- [ ] **World corner bevel prototype (2026-10-21, uncommitted, awaiting user verdict):** `tools/world-bevel`
  rounds convex planar-face corners in BSPs (visual only, collision untouched) -> private `run/codmod/codmod_bevel.pk3`
  (escape1 only; radius 5 adaptive, segments 3, min-length 4, box-corner patches, uv-mode seam). Also writes
  `maps/<map>*.aas` with the AAS header bspchecksum patched (MD4 Com_BlockChecksum of the whole BSP) or bots get
  "aas not loaded". Needs uncommitted rend2 changes in `iortcw/`: ParseFace vert cap 64 -> 1024 and no plane cull on
  non-coplanar faces (tr_bsp.c); VAO cache buffers 65k -> 1M verts (tr_vbo.c, else FPS halves) + `r_vaoCacheStats`.
  In game: FPS within ~5% of stock, AI ok. 199 small strip cracks unresolved. UV morph rejected (squeezed blocks).
  Open: user wants "connected textures" (realign faces vs shader blend); then all maps.
  Curve test: r_subdivisions 1 vs 4 = no visible change, keep default.
- [ ] **SMAA on moving objects (planned 2026-10-21, not implemented):** plan in `docs/smaa-motion-plan.md` (Phase 0 in-game diagnosis at escape1 cages, 1 depth-predicated edges, 2 SMAA+MSAA2x menu option, 3 SMAA T2x with velocity buffer). Phases 1 (`r_smaaPredication`, depth-predicated edges) and 1b (`r_specularAA`, geometric specular AA in lightall_fp) user-checked 2026-10-21 ("good, not game-changing"; may try r_specularAA 2), committed. Flashlight shadow map default 2048 (`codmod_gfxdefaults.cfg`) + "Flashlight Shadow Size" row in GRAPHICS > ADVANCED and engine Effects tab, committed. Next, when the user decides: SMAA T2x phase 3a (camera-only). Sun-shadow ideas (stable cascades + texel snapping, noise-free PCF, cascade blend) analysed in chat, not planned in a doc yet.
- [ ] **Low resolution in fullscreen looks like native (TODO, investigated 2026-10-18, not implemented):** on Wayland SDL
  uses `SDL_WINDOW_FULLSCREEN_DESKTOP` (compositors cannot change video modes), so `r_mode` is ignored in fullscreen and
  `glConfig.vidWidth/Height` become the desktop size. Proper low-res = render at the chosen size into a smaller FBO and
  upscale in the final blit (render-scale option; touches the rend2 present path, needs user verification), or run under
  gamescope. Details in `docs/testing.md` ("Low resolution in fullscreen").
- [x] **Fullscreen switch from the menu rendered in a corner (2026-10-18, user-confirmed, uncommitted):** root cause and fix in `docs/testing.md` ("Soft vs hard vid_restart").
- [x] **Tactical AI overhaul** (`docs/ai-overhaul-plan.md`): [x] Phase 1 cover + OPEN/MOVE/HIDE/PEEK (2026-10-18, user-confirmed, committed); [x] 2 squads/flank/suppress (2026-10-18, user-confirmed); [x] 2b push for an angle (user-confirmed); [x] 3 threat reactions: grenades/dodge/suppression/retreat/morale/opportunism (2026-10-18, user-confirmed, committed); [x] 4 search/hunt: hunt to predicted pos, hold angles, corner clearing, sweep, alert (2026-10-18, user-confirmed, committed); [~] 5 movement/aim polish: backpedal, crouch-walk, jink, kick, accuracy warm-up, campers (`ai_cast_cod_polish.c`, `cod_aiPolish`; 2026-10-20, user-confirmed, committed); [x] 6 difficulty/perf/docs: skill table (`cod_aiSkillScale`), `[ai] perf` counters (cod_aiDebug 2), all 32 maps load, save/load mid-fight OK, `docs/ai-tactics.md` (2026-10-20, user-confirmed, committed)
- [x] **Gameplay options menu (2026-10-18, uncommitted, awaiting in-game check):** MODS > GAMEPLAY, 11 `cod_opt*` toggles (`docs/gameplay-options.md`)
- [x] **Separate the capability from the config that enables it** (2026-10-18: phase 1 merged in PR #2;
  plan in `docs/capability-split-plan.md`). Phase 2 (remove opengl1, SP only): done, merged in PR #3. Goal: the iortcw engine/game modules only *support* the new mechanics, HUD and renderer features;
  `codmod` (the `fs_game` mod: `codmod.cfg`, `codmod_binds.cfg`, menu deltas) is what *activates* them. Running
  without `fs_game codmod` should give vanilla RTCW behavior on the modernized ioRTCW port. Background and current
  coupling: `docs/architecture.md` section 0. Planned steps:
  - [ ] 1. Audit: list every cvar and hard-coded behavior that turns a codmod feature on by default in code
    (`bg_cod.c` table, `cod_enable` default 1, cgame HUD/crosshair, `r_codSpecular`, `r_bloom`, `r_grade`, `r_ao`,
    SMAA, `cl_viewSmooth`, `cod_skipIntro`, ...). Mark each as capability (keep in code) or opinion (move to mod).
  - [ ] 2. Decide the activation mechanism (candidates: engine default 0 and `codmod.cfg` sets 1; or one gate cvar
    such as `cod_enable` set from the mod; or detect `fs_game codmod`). Record it in `decisions.md` and jevmem.
  - [ ] 3. Flip code defaults to vanilla-safe values and move the "on" values to `codmod.cfg`. Respect the
    settings rule in AGENTS.md: user-facing options keep their code default (`CVAR_ARCHIVE`) and reset value in
    `codmod_binds.cfg`; only internal/pinned tuning goes in `codmod.cfg`. Watch latched cvars and savegame load.
  - [ ] 4. Check what must stay engine-side regardless of mod: pmove prediction (`bg_pmove.c` runs for client and
    server and must match), renderer fixes that are bug fixes (sync stalls, flare queries, soft `vid_restart`).
  - [ ] 5. Verify both modes: `fs_game codmod` identical to today (use `scripts/shots.sh` + `shots-diff.py` and the
    bench demo), and without the mod vanilla feel (HUD, movement, menus intact). Do not touch the rend2 present/2D
    path or `wolfconfig.cfg` without user verification (safety rules, `docs/testing.md`).
  - [ ] 6. Update `docs/architecture.md` section 0 ("Current coupling") and README once done.
- [x] **Cutscene lite + Exposure menu** (2026-10-16): `r_cutsceneFx` default 3 (sun+dlights); GRAPHICS Gamma (`r_gamma`) + Exposure (`r_cameraExposure`); awaiting user confirm on escape1 + menus (`docs/testing.md`)
- [x] **Soft vid_restart (MangoHud)** (2026-10-16): mode/FS Apply keeps GL context; hard only for context-attr latches; smoke OK under mangohud Wayland (`vid_restart: soft`, `GLimp_SetModeInPlace`); docs in `docs/testing.md`
- [x] **Video Mode scrollable popup** (2026-10-16): `vidmode_popmenu` / `FEEDER_VIDMODES`; engine `7f342afe`, outer `40f36c7`; also fixed load.menu fadebox missing `}` (delete-confirm parse error)
- [x] Menu cursor: new dagger art, hotspot at the tip, no widescreen stretch; engine `2d81a83e`; user verified 2026-10-16
- [x] Lean aim fix: shots fire from the leaned camera eye (`BG_CodLeanOffset`) + viewmodel lean fade in ADS; engine `3e63880a` + follow-up; confirmed 2026-10-15 (`docs/lean-aim-fix.md`). Gotcha: run `scripts/install.sh` after build
- [x] Flashlight shadows (spot shadow map + screen mask, `r_flashlightShadow`); user verified 2026-10-13
- [x] Flashlight lights static VAO models (escape1 cages, iron gates): three rend2 dlight fixes; user verified 2026-10-13
- [x] Flashlight/dlights now light model entities (characters, props, items) per pixel with spot-cone test (`R_DlightEntity`, cvar `r_dlightEntities` default 1); user approved 2026-10-13. Open: metallic/baked-light items still reflect little
- [x] Settings > Game "Skip Intro" toggle (`cod_skipIntro`, engine `common.c` + `game.menu.delta` + `codmod_binds.cfg`); confirmed 2026-10-13
- [x] Cutscene letterbox bars drawn black; intro always plays (ignores `com_introPlayed`, `+set/+exec` args no longer suppress it); any key skips cinematics — engine commits 5665ad51, 37afbae2; confirmed 2026-10-13
- [x] **Gyro aiming (DualSense):** `cod_padGyro` Aiming/Off/Always + sens, menu rows; playtested OK 2026-10-13 (`docs/gyro.md`)
- [ ] Phase L0 (optional): translate menus and available game data (briefings, strings, codmod menus/HUD) — see docs/phase-l10n.md
- [x] Phase L1: AI-transcribed subtitles + display + Game-menu toggle (committed 2026-10-15)
- [ ] Phase L2 (optional): AI-translate subtitles
- [x] README "Localization (community patches)" section with German/Spanish packs — 2026-10-12
- [x] First-launch defaults: triple buffer, no cap, desktop res, fullscreen; docs/menus.md rules — 2026-10-12
- [x] GRAPHICS > ADVANCED tab + `codmod_gfxdefaults.cfg` (settings persist now) — 2026-10-12, confirmed 2026-10-13
- [x] GRAPHICS menu trimmed to one page (AA, VSync, FPS limit, mode, fullscreen, brightness); pk3 repacked — 2026-10-12, confirmed 2026-10-13
- [x] Phase 5b: health regen, CoD-like stamina, horizontal health/stamina bars (confirmed 2026-10-08)
- [x] Phase 5b follow-up: double ammo + interact hint (“Press F” / “Breakable”) (confirmed 2026-10-08)
- [x] **Phase 3 per-weapon ADS bake** — all 9 from `codmod_ads_tune.log` final pass (2026-10-09); globals 0; `cod_adsCrosshair 2`; `cod_adsCrosshairForce` for re-tune; tooling kept.
- [x] Hip crosshair on Garand + Mauser-with-scope (was vanilla-hidden) — 2026-10-09
- [x] Default `r_gamma 1` in `codmod.cfg` (was 3, incorrect) — 2026-10-16
- [x] Default `r_gamma 3` in `codmod.cfg` — 2026-10-09 (reverted 2026-10-16)
- [x] Phase 5c: CoD HUD — `clip/reserve` ammo, no health/stamina bars, low-HP blood (confirmed 2026-10-09)
- [x] Phase 5c follow-up: CoD 4-post crosshair bloom + ADS post fade (keep center dot) — committed 2026-10-09
- [x] E9 hitmarkers (X flash + body/headshot sounds) + unbind CTRL from `+attack` — committed 2026-10-09
- [x] Hipfire scatter when not ADS (CoD cone of fire) — committed 2026-10-09 (playtest confirm still welcome)
- [x] Semi-auto / pistol / bolt: hold-fire only fires once (click per shot); auto weapons keep hold-to-spray — committed 2026-10-09
- [x] FP fire anim kick lock (weapAnimTimer + clear; committed 2026-10-09)
- [x] Phase 5d: binds reset, toggle crouch, health clamp, flashlight, reload anim — follow-ups committed 2026-10-09; playtest confirm still welcome
- [x] Flashlight beam (`CG_Spotlight` + forced dlights) + save `cameraPortal` crash fix — committed 2026-10-09; playtest confirm still welcome
- [x] Flashlight follow-up: intensity 500, close-wall curve, HUD icon (no world overlay), weapon icon aspect — committed 2026-10-09
- [x] Flashlight spot cones: rend2 `AddSpotLightToScene` + eye-origin dual cone; `r_dlightMode 1` default — built/installed 2026-10-09; playtest confirm welcome
- [x] HD pack SIGSEGV: `ResampleTexture` stack `p1`/`p2` → hunk by `outwidth` (opengl1+rend2) — verified escape1 with `codmod_hd.pk3` 2026-10-09; uncommitted
- [x] Phase 6: slide — confirmed in-game 2026-10-09
- [x] Phase 6b: prone, tier A (gameplay) — confirmed in-game 2026-10-09 (`cod_proneScale 0.55`)
- [ ] Phase 6b: prone, tier B (third-person animations, optional)
- [ ] Phase 7: extras (optional). In progress: E4 ADS sway/breath, then E5 recoil model (next, 2026-10-13)
  - [x] E4 ADS sway/breath: done 2026-10-13, user approved, tuned down to 0.34/0.22 (`cod_adsSway*`)
  - [x] E13 AI sprint: done 2026-10-13, user approved (`cod_aiSprint*`)
  - [x] Fix: empty-clip reload anim sometimes missing (prediction carried weapAnim; cg_predict.c + cg_weapons.c), done 2026-10-13, user confirmed
  - [x] E5 CoD-style recoil model: real aim kick, done 2026-10-13, user approved feel (`cod_recoil*`, `STAT_COD_RECOIL`)
- [x] **Capped FPS below cap fix** (2026-10-14, user-verified, engine `194e7bbe`): the pacer's `glFinish` before the swap (`com_maxfpsGpuSync 1`) serialized CPU/GPU whenever a cap was set that the GPU could not hold (240 cap: 211 FPS, GPU ~80%). Now suspended after 4 missed deadlines, retried with doubling backoff (`Com_PresentWait`, common.c). Bench 240 cap: 211 -> 239 FPS; 144 cap unchanged (sync stays on)
- [x] **Strafe + counter-aim jitter** (2026-10-14, user-verified "super smooth", engine `76e18436`; cl_viewSmooth code default 1 not archived, cg_subMsecLerp pinned in codmod.cfg): predicted view was one frame (4/5 ms) behind mouse look and followed +1/-2 ms clock nudges. Engine view clock `CL_UpdateViewClock` + `com_frameClockUs`, cgame `predictLagMs` (cg_view/cg_predict). A/B `cl_viewSmooth 0`, `cg_subMsecLerp 0`. docs/fps-limiter.md
- [x] **GPU pass savings, 247 -> 303 FPS** (2026-10-14, user confirmed, engine commit 01452ea2): GPU pass profiler (`r_gpuProfile`/`gpuprof`), non-blocking sun query (sun rays now only when the sun is visible), SMAA without copies + stencil (`r_smaaStencil`), GTAO depth mips (`r_ssaoDepthMips`, not bit-exact, visually same), gather AO upsample; `scripts/shots.sh` + `shots-diff.py` for image diffs. See docs/performance.md
- [x] **GPU utilisation 76% -> 97%** (2026-10-14): removed per-frame `glFinish` in `RB_SwapBuffers` (`r_swapFinish 0`) and flare depth readback -> occlusion queries (`r_flaresAsync 1`); bench 183 -> 247 FPS, 1% low 106 -> 165. User confirmed in-game (HUD/menus fine, ~99% GPU); engine commit 0b6f57fc. See docs/performance.md
- [x] **SMAA default (replace MSAA 2x):** implemented + benchmarked +18% (2026-10-12), see `docs/smaa.md`.
- [x] SMAA user canary passed 2026-10-12; committed with engine patches exported.
- [x] **Controller support (Xbox + PlayStation):** CoD4 `PAD0_*` binds, joystick on by default, menu pad nav, original pad glyphs on interact hints (`codmod_pad.pk3`). Built/installed 2026-10-11; pad playtest welcome.
- [x] **Controller polish:** default stick sens half on X / lower Y; pad aim assist + optional auto-aim; CONTROLS → CONTROLLER / MOUSE & KEYBOARD. Built/installed 2026-10-11; playtest welcome.
- [x] **Controller feel:** hold X/Square interact; always-on axial snap, stick EMA, move cardinal snap, target friction; Auto-Aim optional only. Built/installed 2026-10-11; pad playtest welcome.
- [x] **Hold crouch→prone (pad):** `+crouchprone` on Circle/B (~400 ms). Built/installed 2026-10-11; playtest welcome.
- [x] **Pad aim LOS + snap; crouch 160 ms; prone jump = stand only.** Built/installed 2026-10-11; playtest welcome.
- [x] **Crouch+jump stand; Square tap reload/hold use; ADS-only auto-aim; pause SETTINGS hub.** Built/installed 2026-10-11; playtest welcome.
- [x] **Stance/menu UX:** crouch+jump no hop; snappier prone; pad direct prone; SETTINGS overlay fix; B closes pause; focus outline + auto-select. Playtested OK 2026-10-11.
- [x] **Pad-only focus outline:** `in_lastInput pad` only; 3px padding + 1px border. Built/installed 2026-10-11.
- [x] **Pad menu nav:** autofocus top (skip BACK); setfocus/cursor sync; spatial D-pad/stick; A/X cycle values. Built/installed 2026-10-11; playtest welcome.
- [x] **Pad exit + editfield nudge:** Exit popup focus/hover fix; A/X enter edit then pad L/R ±0.05; D-pad kept for selection. Built/installed 2026-10-11; playtest welcome.
- [x] **CoD-style main menu (vertical list):** `mod/codmod/ui/main.menu` → `codmod_menus.pk3` (left stack PLAY/LOAD/OPTIONS/MULTIPLAYER/CREDITS/QUIT; bottom bar chrome hidden). Confirmed in-game 2026-10-09.
- [x] **CoD-style pause menu (vertical list):** `mod/codmod/ui/ingame.menu` in same pk3 (SAVE/LOAD/CONTROLS/OPTIONS/EXIT left stack; SYSTEM merged into OPTIONS). Confirmed in-game 2026-10-09; SYSTEM removed 2026-10-09.
- [x] **E14 higher menu resolutions:** `r_vidModes` 30–41 (2560×1440, 3840×2160, ultrawides, …); UI multi prefers SDL `r_availableModes` when set (else full table + Automatic/Custom). Built/installed 2026-10-09; playtest welcome.
- [x] **CoD-style options/submenu vertical nav:** `setup.menu` hub + system/controls/options (+ ingame_*) section tabs + leave list in `codmod_menus.pk3`. Playtest welcome (2026-10-09).
- [x] **CoD-style settings value pages:** `system`/`options`/`controls` + `ingame_*` fullscreen (left section tabs, right value rows); hub closed/covered so labels no longer collide. Installed in `codmod_menus.pk3` 2026-10-09; playtest welcome.
- [x] **Settings polish:** Main OPTIONS → hub; submenu chrome (`menu_select`/flame) + BACK; CoD `mods.menu` (list + Launch). Installed 2026-10-09; playtest welcome.
- [x] **Fullscreen click SIGSEGV under game_run.sh (MangoHud/Wayland):** FS-only applies use in-place `SDL_SetWindowFullscreen` (desktop FS on Wayland); never fall back to GL destroy/`vid_restart`. Peek latches via `Cvar_LatchedPending` (do not `Cvar_Get`-apply). Verified mangohud+gamemode `+toggle r_fullscreen +vid_restart` → in-place, exit 0 (2026-10-09). Uncommitted with E14/menus.
- [x] **Menu UI fix-up:** pause BACK/Esc → hub; System+Game Options → single Options; all sliders → EDITFIELD decimals (closes E15). Installed 2026-10-09; playtest welcome.
- [x] **Menu layout polish:** mouse settings → LOOK; PERFORMANCE folded into VIDEO; Driver Info as VIDEO entry; `cg_fov` in VIEW (closes E16). Installed 2026-10-09; playtest welcome.
- [x] **Menu hint strip:** mid-screen `yesno_message` → bottom strip; `keyBindStatus` no longer clips (drop `text " "` offset); restore `slider_message`; widen setup `message_*`. Confirmed 2026-10-09.
- [ ] Menu overhaul follow-ups (optional): custom title art
- [x] **E22 HD textures:** world **general-wdn 2×**, fonts **general-wdn 4×** (confirmed 2026-10-09; ultrasharp/animevideov3 rejected); dual-model batch + `pack --merge`; local `codmod_hd.pk3` (~272 MiB); `r_picmip 0`.
- [x] **Wall/POM normals experiment:** smoke → full SP `_n` pack → A/B → **removed** (pack + `tools/pom-bake`); kept rend2/SSAO and related non-POM fixes (2026-10-09).
- [x] **rend2 SSAO default:** `r_ssao 1` in `codmod.cfg` + `run.sh` latch (playtest OK 2026-10-09).
- [x] **rend2 graphics pack:** MSAA 2, AF 16, float LM, specular/deluxe, forceSun + rays, soft 2048 cascades — cfg + latch (playtest OK / kept 2026-10-09). No `*_s` pack yet.
- [x] **Uncap FPS:** `seta com_maxfps "0"` in `codmod.cfg` (2026-10-09).
- [x] **Default sound levels:** Effects `s_volume 0.489583`, Music `s_musicvolume 0.510417` in `codmod.cfg` + system menus (2026-10-09).
- [x] **Blank Sound Quality menu:** removed dead `s_khz` rows from sound menus (2026-10-11).
- [x] **E23 HD audio tool + recipe lock:** `sr_only` + music `sr_linked`; `tools/hd-audio/remaster.sh` (batch+pack+resume) documented; full pack awaits user GPU time (2026-10-11).
- [x] **E23 full pack:** built 2026-10-12 (1360 files, 556 MB) -> `run/codmod/codmod_hd_audio.pk3`, auto-loaded; 2 files used plain-resample fallback (e.g. blank.wav). Awaiting user playtest (remove pk3 to revert).
- [x] **Graphics options subtabs:** VIDEO → DISPLAY/QUALITY/EFFECTS; cull NV/ATI/legacy footguns; expose rend2 defaults (SSAO, MSAA, AF, HDR, sun shadows, …). Packaged in `codmod_menus.pk3` 2026-10-11; playtest welcome.
- [x] **Hub OPTIONS→GRAPHICS; SOUND + GAME pages:** VIEW renamed GAME; move sound/game out of graphics menu; drop vanilla crosshair size/alpha/preview + `cg_viewsize`. Installed 2026-10-11; playtest welcome.
- [x] **Bench abort → no HUD / no pause:** escape1 cutscene `cameraMode` left stuck; cleanup now `stopCamera` + clear client cam. Built/installed 2026-10-11; playtest welcome.
- [x] **HUD/UI guardrails + config wipe:** orphan fullscreen UI no longer skips cgame; `codmod.cfg` + `run.sh --reset-config` force `cg_draw2D`/`cg_drawGun`; wolfconfig wiped 2026-10-11 (saves kept).
- [x] **Benchmark (rebuilt):** real-time demo replay (`cl_benchDemo`, µs frame stats) + `scripts/bench.sh` + DISPLAY "RUN BENCHMARK" button; demo `mod/codmod/demos/codmod_bench.dm_50`. Engine change client-only (cl_cgame/cl_main/client.h/sys). CLI smoke OK 2026-10-11; **user to verify menu button + HUD/ESC pause**. Docs: `docs/performance.md`.
- [x] **Frame-perfect FPS limiter + vsync modes:** all plan steps done 2026-10-12 (committed; confirmed 2026-10-13). `Sys_WaitUntil`, pacer modes 0/1/2, `r_vsync` 0-4 (Off/On/Adaptive/Triple/Low latency), sub-ms cgame lerp, DISPLAY menu rows (menus pk3 repacked). Details + results: `docs/fps-limiter.md` section 6. Open: Windows untested; vsync 1-3 not validated on this Wayland box.
- [x] **HRTF 3D audio:** OpenAL Soft `ALC_SOFT_HRTF` via `s_alHRTF` (default on) + sound-menu row; effects volume 1.0. Playtested OK 2026-10-12. Ideas left: EFX reverb per area, low-pass occlusion.
- [x] **Kick buff + R3 tap/hold:** `cod_kickDamage` was 50, back to vanilla 15 on 2026-10-20 (too strong); pad R3 `+quickkick` = tap quickknife / hold kick. Playtested OK 2026-10-12. Docs: `phase-5-feel.md`.
- [x] **iortcw fork published:** all 83 engine paths on `illescasDaniel/iortcw` `cursor/codmod-engine-0f47` (+ `codmod` mirror) match local `git am` of `patches/`; PR https://github.com/illescasDaniel/iortcw/pull/2 (2026-10-12; #1 closed — staging Action reds only).
- [x] **Outer uses fork:** `setup.sh` clones `illescasDaniel/iortcw` branch `codmod` (no `git am`); `patches/` kept as `export-patches.sh` backup (2026-10-12).
- [x] **HD cutscene videos (2026-10-13):** `tools/hd-video` (SPAN 2x -> MJPEG/AVI, `pilot`/`batch`/`pack`) + engine AVI path (`cl_cin_avi.c`, `CIN_PlayCinematic` prefers `video/<name>.avi` over `.roq`, JPEG linked into client). Intro 1024x512 115 MB + menu loops packed to `run/codmod/codmod_hd_video.pk3` (private). Engine built/installed; headless smoke test plays + exits clean. Committed; confirmed 2026-10-13. MP videos out of scope.

- 2026-10-13 HD video: recipe chosen = `nlm1+span` (ffmpeg nlmeans s=1:p=5:r=9, then 2xLiveActionV1_SPAN, 2x, dynamic grain 3 added after upscale). `hd-video batch --variant nlm1+span --grain 3` + `pack --variant nlm1+span` done (wolfintro/menu/menu2, 130 MB pk3 installed). Aspect (2.37:1 letterbox fit) approved by user. Confirmed 2026-10-13.

- [x] **SSAO option A (2026-10-13):** stock rend2 `ssao_fp.glsl` rewritten (view-space normals, 16-sample spiral with IGN noise, world-unit radius from FOV, distance falloff, view model/sky masked via depth <=0.3 / >=0.99999). New cvars `r_ssaoRadius` (40), `r_ssaoStrength` (1), `r_ssaoSamples` (16), uniform `u_SsaoParams`. Committed; confirmed 2026-10-13. Next: option B (GTAO) per plan.
- [x] **SSAO option A, part 2 (2026-10-13):** new `ssaoup_fp.glsl` (depth-aware bilateral upsample of the half-res AO + distance fade 1500-4000, sky/viewmodel = 1) replaces the plain multiply blit in `RB_PostProcess`; `depthblur_fp.glsl` USE_DEPTH tolerance is now relative (3% of depth + 1.5 units). Bench uncapped 171 -> 175 FPS (no cost). Committed; confirmed 2026-10-13.
- [x] **GTAO (2026-10-13):** `ssao_fp.glsl` has a `USE_GTAO` variant (`r_ssaoMode 1` default; 0 = hemisphere), half-res depth `ssaoDepthImage` for AO/blur/upsample. Default 2 slices x 4 steps = 192 FPS vs 255 with SSAO off (bench uncapped). Details + cost table in `docs/ssao.md`. Committed; confirmed 2026-10-13. Idea left: depth mips, ambient-only application in `lightall`.

- AO menu option: `r_ao` (0-4) live-switchable in GRAPHICS; `r_ssao` is now derived, pins removed from run.sh/gfxdefaults. Confirmed 2026-10-13.

- Ambient-only AO (r_ssaoAmbient 1, default) via lightall + full-res aoImage; depth mips tried, no gain, removed.

- [x] **Menu FPS limit (2026-10-13):** `com_maxfpsMenu` (-1 Auto/monitor refresh default, 0 Off, fps) caps only menu/cinematic/pause frames (`CL_InMenuOnly`); `com_maxfps -1` = Auto too (default stays Off). GRAPHICS row "Menu Frame Rate Limit", labels `Auto (%hz)` expanded in `ui_shared.c`. Committed; confirmed 2026-10-13. See `docs/fps-limiter.md`.

- 2026-10-16: Multi-language support (text packs de/es, main-menu selector, subtitle size field, English transcript fixes) committed.

- 2026-10-16: Jack's glasses floating above his face in cutscenes fixed (awaiting user in-game check). Cause: the AO apply blit (`FBO_Blit` in `RB_...` between the opaque and translucent draw lists, rend2 `tr_backend.c`) left the GL viewport at full screen while the cutscene view was letterboxed, so translucents (sort 5 glasses) were drawn offset from the opaques. Fix: `SetViewportAndScissor()` after the blit.
- 2026-10-16: Cutscene letterbox bars removed (`cg_view.c` no longer shrinks refdef for `cg_letterbox`; black bar fill dropped from `cg_draw.c`). Awaiting user check.

- World bevel round 7 (2026-10-21, uncommitted): wall-end caps + mitred L bends (`--wall-ends`, `--mitre`, default on) and `--min-angle 15` pack installed as run/codmod/codmod_bevel.pk3 (previous round-6 pack backed up in session scratchpad). Cracks 197-223. Run ends still tapering: 5667 no_plane, 2547 no_hole; thin-face (1-unit sliver) rejects near start plinths. Next: user verdict, then connected textures, then cracks. Perf idea: vectorise match_edges in numpy (6-7x on that stage), profile whole tool before any Go/Julia port.
- World bevel connected textures (2026-10-21): measured on escape1 (min-angle 15): 5582 same-shader seams (mean phase mismatch 0.27 texture period), 2681 different-shader seams (cannot align), 102 scale-mismatch. Morph over the 5-unit strip squeezes blocks (rejected); realigning whole faces cascades across each face's other edges. Dropped as not worth it. White-slit fix (match_edges seam trimming) verified in game; `--min-angle 15` pack installed. Corner spots near the start left as-is. Next: round other 3D assets (weapons, props).
- World bevel `--uv-mode align` prototype (2026-10-21): shifts whole coplanar face components' st by the non-integer seam mismatch (greedy forest, longest runs first); 3265 components shifted, 2126 other-shader/561 drifting/75 scale skipped. In-game A/B on 4 escape1 views (benchmarks/shots/align_cmp.png): barely visible. Not made default; installed pack stays fix_ma15 (seam mode).
- World bevel align v2 (2026-10-21): strip st now unfolded by arc length from each face's cut line (not plane projection) and align measured at the unfolded points; stone courses wrap continuously at user's 3 spots. Installed.
- MDC smoothing (2026-10-21, uncommitted): tools/model-smooth/mdc_smooth.py smooths weapons (models/weapons2/*) into run/codmod/codmod_smooth_mdc.pk3 (installed). Viewmodels checked on banks 2-7: rounder scopes/grenade, no artifacts. Next: heads (head.mdc), props, perf check, user verdict.
- MDC pack widened (2026-10-21): weapons + heads (helpers ride on main surface) + player acc + powerups + mapobjects + furniture + ammo + flags (481 files) installed as codmod_smooth_mdc.pk3. BJ head and escape1 views checked, no artifacts seen; FPS not benchmarked yet. Not covered: gibs, shards, players/*/armor.
- MDC pack now covers every .mdc in pak0 except foliage/sky/UI/shards (638 files, 17.7 MB) as codmod_smooth_mdc.pk3; default --exclude in mdc_smooth.py. Torches/cage lights etc. are baked misc_model surfaces in the BSP (not covered): next = trisoup smoothing in world tool.
- MDC pack fix (2026-10-21): smoothed pistol viewmodels (Colt/Luger/Colt2 `v_*`) and all `models/weapons2/*/v_*_barrel*` parts looked ragged at the rear sight (small overlapping parts displaced independently, not a texture problem). Now in `DEFAULT_EXCLUDE` of `mdc_smooth.py`; pack rebuilt (572 models) and verified in ADS with `give Luger`/`give Colt`. Next: baked-model (BSP trisoup) work, then FPS benchmark.
- Baked models (2026-10-21): `world_bevel.py --smooth-models` Loop-smooths trisoup misc_model surfaces (escape1: 208 surfaces, 17k->69k tris) with the bevel in one BSP. Checked in game on chandelier, cage light, pendant lamp: rounder, no artifacts. Installed `run/codmod/codmod_bevel.pk3` = align + min-angle 15 + smooth-models for escape1. Not yet run on other maps; FPS benchmark still pending.
- Brush props (2026-10-21): the escape1 torch is brush faces (type 1), not trisoup, so the first baked pass missed it. `smooth_brush_props` in `world_bevel.py` smooths them (102 props). Installed `codmod_bevel.pk3` = bevel + trisoup + brush props; torch geometry confirmed 256 -> 676 tris, visual check by the user pending (my screenshot camera was not repeatable).
- FPS benchmark (2026-10-21, bench demo, 2561x1601): smoothing packs on 211.8 avg / 131 1%-low vs off 213.5 / 135 (median of runs 2-3). No measurable cost; a one-off slow first launch after swapping a pk3 is a cold-cache effect, not geometry. Torch spot on escape1 181-190 FPS with and without.
- Julia port (2026-10-21): `tools/world-bevel-jl/` (stdlib only + Zlib_jll) reproduces world_bevel.py: escape2 8.2 s vs 78 s Python, escape1 ~9 s vs 110 s. Matches Python except float-rounding noise (≈1% of surfaces ±1 vert, 17 surfaces st differ). Not ported: --validate/--roundtrip/--obj/--all; morph/row-tol/surface-type tri untested. Escape2 pack installed as `run/codmod/codmod_bevel_escape2.pk3` for the user's in-game check; not committed yet.
- All maps (2026-10-21): `scripts/build-world.sh` built `run/codmod/codmod_bevel_MAP.pk3` for all 32 maps with the Julia port in 3 min 12 s, no failures; village1/castle/dam load clean (no errors in log). Old `codmod_bevel.pk3` replaced by the per-map packs. Only escape1/escape2 inspected visually; other maps not yet checked in game.
- Connected textures + corner lighting (2026-10-22): user accepts the current state ("okay for now"), uncommitted, all 32 maps rebuilt (plans `docs/bevel-lighting-plan.md`, `-2.md`; repro `scripts/shot-at.sh` + `benchmarks/spots-tram.txt`, `scripts/seam-metric.py`). Done: post-cut wall caps (white hole), per-strip lightmap chart (8-unit rows), signed-graph texture flips (mirror 22% -> 0.6%), different-shader wrap (narrow face owns the curve), IRLS offset solve, `--align-stretch`. FUTURE IDEAS (not planned): (a) geometric transition band (second `cut_face!` split at r+W, shared texture/light chart; `--soft-width` is parsed but unused) for the visible step at strip edges and slope kink; (b) 21% of tram seam length still has a real 0.15-0.5 period texture offset from loop (cycle) conflicts, 23% different-shader seams, 21% rotated-axis seams (ledges/tops) left alone; (c) spot 5 (3908 1784 1272) regressed slightly: faint line at a strip edge; (d) overlay cross-fade surface for different-shader corners (needs leafsurface remap + generated blend shader); (e) q3map2 relight for physically right corner light; (f) 4 tram faces use lightmap fallback; the uvgrid debug shader was never run in game; (g) escape1/village1 render black under `shot-at.sh` (intro script), so only tram/trainyard were checked.
- Bevel lighting P0-P4 (2026-10-22, uncommitted, plan in docs/bevel-lighting-plan.md): post-cut wall-cap fix (hole at tram spot02/05 gone), per-vertex lightmap blocks in appended pages (`lmblend.jl`, `--no-lm-blend` to disable; fallback faces <=0.7% on all 32 maps, 0 non-finite), global least-squares texture alignment (`--uv-mode align`; `align-greedy` keeps the old one; `--align-stretch` parsed but not implemented). Tram seam jumps (lit, scripts/seam-metric.py) 29.7/15.6/0.6/8.4/5.2 -> 22.7/2.7/0.7/3.5/1.8; align 91.9% of seam length within 0.05 period. All 32 packs rebuilt with `scripts/build-world.sh` (now `--stats`). Known defect: strips whose faces differ in light show a ~10% dip band vs both neighbours (tram spot01 x 620-720); spot01's 674 seam is a different-shader seam. shot-at.sh on escape1/village1 renders black (also without our pack), trainyard checked instead. Side-by-side: benchmarks/shots/tram_base_vs_final.png.
- Bevel lighting round 2 (2026-10-22, uncommitted, docs/bevel-lighting-plan-2.md): P5 diagnostics (`--debug-lm class`, `--debug-shader uvgrid`, `--probe-spot`, `--seam-report`), P6 sub-row chart (chart-vs-face deviation p95 0.151 -> 0.011, 158 pages), P7 orientation flips (`--flip`, signed-graph solve; mirrored area 22% -> 0.6%) done and installed for all 32 maps (build-world.sh, no failures). NOT done: P8 soft light band, P9 different-shader corners (tram spot04/01/06 still show a hard vertical split). Metrics: scripts/seam-metric.py v2; side-by-side benchmarks/shots/tram_r2_baseline_vs_final.png. uvgrid not yet tested in game.
- Bevel lighting round 2 completed (2026-10-22, uncommitted): added P9 (different-shader seams: the narrower face's shader/mapping wraps the whole curve, `--wrap-prefer narrow|wide|off`), reduced P8 (half-smoothstep light fade across the strip, IRLS in the texture-offset solve (good seam length 76% -> 83%), leftover offsets <=0.15 period spread over the strip via `--align-stretch 0.15`). Not done: the geometric transition bands (`--soft-width` still unused). All 32 maps rebuilt, non-finite 0, fallback faces <=0.7%. Known defects: material step at the strip edge on different-shader corners, 21% of same-shader seam length with real offset 0.15-0.5 (cycle conflicts).
- Parallax perf (2026-10-22): phase 1 (sun shadow march opt-in bit, plateau early-out, flat-texture skip, dlight early-out) and phase 2 (footprint/LOD stepping, u_ParallaxParams2) committed; relief+shadows 196 -> 258 fps. Two-row menu done. [ ] Investigate fast-mouse-movement FPS drop (user report, all settings). [ ] Maybe pull r_parallaxFadeDist in; compression only if measured worthwhile.

- SMAA T2x + velocity + MDS limb motion + simplified AA menu (2026-10-22): committed and pushed; READMEs refreshed with the graphics features. Guard eyes (h_blink lid) fixed in `mdc_smooth.py` (supersedes 'helpers ride on main surface' for skin-copy lids).

- Frame warp: [x] Stage 0 verified; [x] Stage 1 (now mode 3, non-viable); [x] `r_frameWarp` menu toggle; [x] stage LL late-latch (user-verified 2026-10-25); [ ] AP-0 timing spike; [ ] AP; [ ] mesh 6-DoF; [ ] entity motion. Details: docs/frame-warp.md.
