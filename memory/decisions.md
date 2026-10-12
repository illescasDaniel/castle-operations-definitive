# Technical decisions

Append-only log, newest first. Never rewrite history: if a decision is reversed, add a new entry that says so.

<!-- Copy this block to the top for each new decision.

## YYYY-MM-DD: <short title>

- **Context:** <what forced a choice>
- **Decision:** <what we chose>
- **Rationale:** <why, and what we rejected>
-->

## 2026-10-12: Fork default branch is `main`; `codmod` and patches branches deleted

- **Context:** After merging fork PR #2 into `master`, `codmod` (ancestor, identical tree) and `cursor/codmod-patches-0f47` (identical tree, bot history) were redundant.
- **Decision:** Renamed fork `master` to `main`; `setup.sh` clones `main`, `export-patches.sh` exports `upstream-pin..main`; redundant branches deleted. Supersedes `IORTCW_BRANCH=codmod` below.
- **Rationale:** One branch to track; the fork is no longer a pure upstream mirror, so `main` is the codmod engine.

## 2026-10-12: setup.sh clones illescasDaniel/iortcw codmod (no git am)

- **Context:** Engine changes lived as `patches/` applied by `setup.sh` onto upstream ioRTCW; the fork now carries those commits on branch `codmod` (PR [#2](https://github.com/illescasDaniel/iortcw/pull/2); #1 closed).
- **Decision:** Default `IORTCW_REPO=https://github.com/illescasDaniel/iortcw.git`, `IORTCW_BRANCH=codmod`; `setup.sh` clones that branch and no longer runs `git am`. Keep `patches/` + `export-patches.sh` as a backup mirror of `upstream..codmod`.
- **Rationale:** One source of truth for the engine (the fork); outer repo stays self-describing via the patch series without re-applying it on every fresh clone.

## 2026-10-12: Publish iortcw fork via Github MCP + Action staging (not git push)

- **Context:** Cloud agent env only lists `castle-operations-definitive`, so `cursor[bot]` `git push` to `illescasDaniel/iortcw` is 403. Github MCP can write as the user, but large `push_files` payloads are awkward.
- **Decision:** (Superseded: the fork now holds the real commit history, force-pushed from the local clone.) Upload the 83 patched engine paths onto `cursor/codmod-patches-0f47` (and mirror branch `codmod`) via Github MCP / Action staging; open PR to `master`. Temporary probe/workflows removed after verify; keep `CODMOD.md`.
- **Rationale:** Delivers the fork without a PAT or adding iortcw to the cloud env repos list. Content verified byte-identical to local `git am` of `patches/`.

## 2026-10-12: Menu deltas v2 store reused original passages as references, not text

- **Context:** Pre-publish legal review found ~2,500 of 3,600 added delta lines also existed in RTCW's menus (moved blocks, copies between menus), so "no original text in git" was not literally true.
- **Decision:** `scripts/menus.py` delta format v2: unchanged ranges stay implicit; any run of lines that exists in an original (the base or another menu, found via a line index) is written as `=<pak path> a b` plus a `#src <path> sha256=` header, verified like the base. Only braces/blank lines and ~75 distinct one-line property assignments with different indentation stay literal (`name back`, `border 0`...). Round-trip checked byte-identical against the previous generated menus and pk3.
- **Rationale:** Makes the repo claim true without a fragile heuristic; costs ~15 KB more delta text. Remaining gap: `ui/menus.txt` and `ingame.txt` (file lists, ~2/3 verbatim) stay tracked whole.

## 2026-10-12: RTCW-derived menus are not in git; deltas + build script instead

- **Context:** `.menu` files are edited copies of RTCW's UI game data (not GPL); a public repo must not redistribute them.
- **Decision:** Track `mod/codmod/menu-deltas/*.delta` (added/changed lines + replaced original line ranges, no original text). `scripts/menus.py` (run by `build-menus.sh`, `setup.sh`, `install.sh`) rebuilds `ui/*.menu` from the user's paks (SHA-256 checked) and packs `codmod_menus.pk3` / `codmod_hud.pk3`; all generated files are git-ignored. Dev flow: edit `ui/*.menu`, `build-menus.sh --export`, commit deltas.
- **Rationale:** Automated for us and for installers; diff/patch formats were rejected because they embed removed original text. `menudef.h` (GPL source), txt lists and glyphs stay tracked. Git history still contains the old menus: squash/rewrite history before publishing.

## 2026-10-12: GRAPHICS > ADVANCED tab with labelled defaults (reverses part of the menu cut)

- **Context:** One short page hid which values the game ships with; the user wants players to see them.
- **Decision:** ADVANCED tab (both options menus) with a warning note, rows for shadow size/filter, SSAO, sun rays, dynamic lights, AF, texture filter, picmip x2, lod bias, frame pacing; recommended value tagged "(default)"; "Restore recommended defaults" button execs `codmod_gfxdefaults.cfg`.
- **Rationale:** These cvars were `seta`-forced in `codmod.cfg` and `+set` in `run.sh` every launch, so menu choices never persisted. Moved to `codmod_gfxdefaults.cfg` (exec'd by `codmod_binds.cfg` on first launch/reset); `run.sh` now `+set`s the latched ones only while wolfconfig has no saved value. Depth prepass, force sun, HDR chain etc. stay pinned and hidden (coupled, see benchmarks).

## 2026-10-12: GRAPHICS menu cut to one page of rows that matter

- **Context:** ~40 rows over DISPLAY/QUALITY/EFFECTS; benchmarks showed most had ~0 effect, were coupled to the sun/shadow pipeline, or were re-pinned by `codmod.cfg`/`run.sh` every launch.
- **Decision:** Single GRAPHICS page: Video Mode, Fullscreen, VSync, Frame Rate Limit, Anti-Aliasing, Brightness (conditional), Driver Info, RUN BENCHMARK (main menu only), Apply. Removed quality preset, Frame Pacing (stays 2), textures/filter/AF/lods, lightmap/specular/deluxe/shadow-filter/prepass, HDR chain, sun rows, SSAO, Shadow Map Size, dynamic lights, sky, marks/brass/corona/particles.
- **Rationale:** SSAO and shadow size are pinned by `codmod.cfg` + `run.sh` (latched), so menu rows would not persist. Defaults unchanged; `wolfconfig.cfg` untouched.

## 2026-10-12: SMAA 1x High replaces MSAA 2x as the default AA

- **Context:** MSAA 2x cost ~28% FPS and missed alpha-tested edges.
- **Decision:** SMAA 1x (iryoku/smaa, MIT) as a rend2 pass in `RB_PostProcess` after tonemap, before 2D; `r_smaa` 0-4, codmod default 3, MSAA default 0. `RB_SwapBuffers`/2D path untouched.
- **Rationale:** Bench: SMAA 3 225 FPS vs MSAA 2x 190 (+18%), no AA 261. Attribution in `docs/credits.md`.

## 2026-10-11: Benchmark = real-time demo replay + µs stats (timedemo rejected)

- **Context:** Rebuilding the shelved benchmark without renderer/camera/present changes.
- **Decision:** Replay a recorded demo with plain `demo` + `cl_benchDemo 1` and time each frame in µs; no `timedemo`, no engine renderer edits. Engine patch limited to `cl_cgame.c`, `cl_main.c`, `client.h`, `qcommon.h`, `sys_unix.c`, `sys_win32.c`.
- **Rationale:** `timedemo` steps 50 ms of game time per frame: the ~23 s demo became 503 frames in 3.6 s (too few for 1% lows, unrealistic). Real-time replay gives ~2000 frames/run.

## 2026-10-12: HRTF 3D audio via OpenAL Soft (no new library)

- **Context:** user asked about OpenAL Soft / libspatialaudio / Steam Audio for HRTF, preferably MIT-ish licensing.
- **Decision:** keep the existing OpenAL Soft backend; request HRTF through `ALC_SOFT_HRTF` context attributes (`s_alHRTF` 0/1/2, `s_alHRTFProfile`), live reset via `alcResetDeviceSOFT`, menu row in sound menus. Details in `docs/audio-3d.md`.
- **Rationale:** sources were already 3D-positioned; the HRTF just was never requested (auto mode only triggers on detected headphones). Steam Audio/libspatialaudio add a mixer replacement for little gain.

## 2026-10-11: Shelve failed benchmark attempt; real cause of missing HUD/pause was rend2 MSAA present

- **Context:** No HUD and no visible pause menu in-game. The two entries below blamed cutscene camera / orphan fullscreen UI; both were wrong.
- **Decision:** Real cause: a rend2 "perf" edit made `RB_PostProcess` leave the final frame in `tr.msaaResolveFbo` and `RB_SwapBuffers` present that FBO directly. All 2D (HUD, menus) draws into `tr.renderFbo` *after* post-process, so with MSAA on (`r_ext_framebuffer_multisample 2`, our default) every in-game 2D element was discarded. The whole engine side of the attempt (bench code, rend2 perf pass, HUD/camera hacks, flashlight single cone) is shelved in iortcw `git stash` "failed benchmark attempt (engine: …)"; `ui_shared.c` pad nav work kept. Engine rebuilt and installed from clean tree.
- **Rationale:** Never present a post-process FBO directly: the 2D pass must reach the backbuffer. Any MSAA-resolve shortcut has to happen after 2D, not after the 3D post-process. Entries below are superseded.

## 2026-10-11: HUD guardrail — orphan fullscreen UI must not skip cgame

- **Context:** After GRAPHICS tooling, HUD and pause stayed dead; `\stopCamera` / `\cod_fixui` were insufficient. Root cause: a fullscreen menu left `WINDOW_VISIBLE` after `KEYCATCH_UI` was cleared so `SCR_DrawScreenField` skipped all `CL_CGameRendering`.
- **Decision:** (1) If `CA_ACTIVE` and fullscreen UI without UI catcher → `UIMENU_NONE`. (2) `codmod.cfg` + `run.sh` force `cg_draw2D`/`cg_drawGun`/`r_finish`/`cod_benchActive` every launch. (3) `--reset-config` wipes `wolfconfig` (keeps saves).
- **Rationale:** One-shot console recovery fails when the user is not on our binary/session; archive cvars and ghost menus need structural guardrails.

## 2026-10-11: Bench cleanup must stop escape1 cutscene camera

- **Context:** Failed/aborted GRAPHICS benchmark left no HUD and no pause menu; wolfconfig already had `cg_draw2D 1` / `cod_benchActive 0`.
- **Decision:** `CL_CodBenchmarkCleanup` and the active-bench update path clear `cl.cameraMode` / `cg_letterbox` and issue `stopCamera`; cgame bench path calls `trap_stopCamera` when it sees an active cam (not only clears `cg.cameraMode`).
- **Rationale:** escape1 intro cam hides all 2D via `cg.cameraMode` and eats ESC via `cl.cameraMode`; clearing `cod_benchActive` alone does not restore HUD/pause.

## 2026-10-11: Keep D-pad for menu selection nav

- **Context:** Temporarily no-op'ing D-pad Down left autofocus stuck on the top row so pad Up/Down appeared broken.
- **Decision:** D-pad Up/Down/Left/Right all move menu focus again; value changes stay on A/X (cycle) or editfield left/right ±0.05.
- **Rationale:** Selection needs the full D-pad; disabling Down made menus undrivable.

## 2026-10-11: Exit overlay focus; editfield pad nudge ±0.05

- **Context:** Exit menu stole no pad focus (title button) and mouse hover selected pause items behind; settings editfields needed a distinct edit flow from cycleables.
- **Decision:** `ingame_leave` is `popup` with decoration title + named focus targets; `Display_MouseMove` / non-mouse `Display_HandleKey` use the focused menu only; skip actionless BUTTON/TEXT in autofocus; A/X enter editfields then pad left/right nudge by 0.05.
- **Rationale:** Overlays must own input; cycleables keep face-button cycling while decimal rows need an explicit edit mode.

## 2026-10-11: Spatial pad menu nav; A/X cycle values; focus sync

- **Context:** SETTINGS/submenus didn't autofocus the first row (BACK won); returning from SETTINGS painted SINGLEPLAYER while cursor stayed on SETTINGS; pad left/right changed cvars so tabs couldn't reach detail rows.
- **Decision:** Clear stale item focus on activate/close; `setfocus` updates `cursorItem`; autofocus top-left skipping BACK; D-pad/left-stick move focus spatially; remove pad D-pad from `UI_SelectForKey` and use A (next) / X (prev) for multi/yesno/slider values.
- **Rationale:** CoD-style two-column settings need directional focus, not list-order wrap onto BACK, and face buttons for value edits.

## 2026-10-11: Pad-only menu focus outline (padded 1px)

- **Context:** Focus outlines helped pad nav but were unnecessary with a mouse cursor; the 2px flush border felt heavy.
- **Decision:** Draw the focused-item outline only when `in_lastInput` is `pad`, inset with 3px padding and a 1px border.
- **Rationale:** Pad still needs a selection cue; mouse/kb already have the cursor.

## 2026-10-11: Crouch-jump stands only; direct pad prone; menu focus UX

- **Context:** Jump from crouch still hopped; prone toggles felt delayed; pad hold Circle crouched then proned; SETTINGS overlaid pause; B didn't close pause; pad menus had no selection cue.
- **Decision:** Latch `PMF_JUMP_HELD` when `PM_CheckDuck` stands the player. Shorten prone times (250/250/100) and allow toggle during cooldown. `+crouchprone` waits for release (tap=crouch) or hold threshold (direct prone). SETTINGS is fullscreen and closes `ingame` first. ESC/B on non-fullscreen menus unpauses; every menu auto-focuses the first item and draws a focus outline.
- **Rationale:** CoD stance rules + readable pad menus without leaving pause chrome underneath.

## 2026-10-11: Square tap reload / hold use; ADS-only auto-aim; pause SETTINGS

- **Context:** Jump did not clear sticky crouch on pad; reload felt broken after Square became use-only; Auto-Aim snapped while hipfiring; pause listed CONTROLS/GRAPHICS/SOUND/GAME flat.
- **Decision:** Clear sticky crouch on any jump key (SPACE/pad A/`+moveup`). Bind `PAD0_X` to `+reloaduse` (tap=`+reload`, hold=`+activate`). Auto-Aim snaps only while ADS onto closest LOS target; hipfire with Auto-Aim on has no angle pull. Pause hub is SAVE/LOAD/SETTINGS/EXIT with SETTINGS opening the four pages.
- **Rationale:** Matches CoD Square reload + hold interact; console auto-aim is an ADS feature; cleaner pause IA.

## 2026-10-11: Pad aim LOS + snap; slower crouch; prone jump stands only

- **Context:** Aim assist pulled through walls; Auto-Aim felt like slow drag not console snap; crouch (70 ms) too fast; jump from prone stood and launched.
- **Decision:** Require `MASK_SOLID` LOS for pad friction/magnetism/auto-aim; Auto-Aim snaps hard onto visible targets (wider cone); `cod_duckTime` 160 ms; jump-to-exit-prone sets `PMF_JUMP_HELD` and blocks jump during prone transition.
- **Rationale:** Match console CoD expectations; crouch timing is shared KB/pad view lerp.

## 2026-10-11: Pad Circle/B hold → prone (tap crouch)

- **Context:** User expected CoD-style hold Circle/B while standing or walking to go prone; `togglecrouch` is press-only so hold did nothing.
- **Decision:** Bind `PAD0_B` to `+crouchprone`: press crouches (or exits prone); hold ≥400 ms enters prone; short release while already crouched stands. Keyboard `C` stays `togglecrouch`. D-pad Down remains direct `+prone`.
- **Rationale:** Matches console CoD crouch/prone without a settings toggle; sprint+crouch slide still wins while sliding.

## 2026-10-11: Pad interact on X/Square; always-on stick filters + friction

- **Context:** User wanted CoD-style hold Square/X to interact (not D-pad Up), plus always-on axis snapping, stick smoothing, move cardinal snap, and target friction — no toggles for those.
- **Decision:** Bind `PAD0_X=+activate`, move reload to `PAD0_DPAD_UP`. Apply EMA smoothing + axial look snap + move cardinal snap in `IN_GamepadMove` after deadzone. Target friction/magnetism always runs for pad last-input in `CG_CodPadAimAssist`; keep only `cod_padAutoAim` as an optional stronger ADS chest pull. Remove `cod_padAimAssist` cvar/menu toggle.
- **Rationale:** Matches console CoD expectations; filters are feel infrastructure players assume, not settings.

## 2026-10-11: Pad sens half/Y-lower + aim assist; CONTROLS hub split

- **Context:** Default stick look was too fast; user wanted CoD-style aim slowdown near enemies, optional auto-aim, and a CONTROLLER settings page separate from keyboard binds.
- **Decision:** `cod_padSensX` 0.5 / `cod_padSensY` 0.35 (multipliers on `j_*`); `cod_padAimAssist` 1 (slow near enemies); `cod_padAutoAim` 0 (chest pull on ADS). CONTROLS hub opens CONTROLLER or MOUSE & KEYBOARD. Assist is pad-only via `in_lastInput`.
- **Rationale:** Matches common FPS pad defaults; auto-aim opt-in; mouse path unchanged.
- **Superseded (friction toggle):** 2026-10-11 entry above makes friction always-on and drops `cod_padAimAssist`.

## 2026-10-11: CoD4 pad layout + original Xbox/PS glyphs

- **Context:** Engine already had SDL GameController (`PAD0_*`) but `in_joystick` was off and codmod shipped no pad binds/UI/glyphs.
- **Decision:** One CoD4-style `PAD0_*` bind map for Xbox and PlayStation (SDL positional map); enable `in_joystick` + analog sticks by default; menu nav on D-pad/A/B/Start; original copyright-free Xbox-like / PlayStation-like glyphs in `codmod_pad.pk3` for interact hints; family via `in_gamepadFamily` from `SDL_GameControllerGetType`.
- **Rationale:** Same layout as the mod’s CoD4 feel; no official TM button art; `in_lastInput` switches F vs D-pad glyph so KB/mouse users keep “Press F”.

## 2026-10-11: Project scope is remaster (gameplay + HD presentation)

- **Context:** Music `sr_linked` A/B landed as a true remaster; user asked to widen the project beyond “CoD-movement mod.”
- **Decision:** Frame `codmod` as an SP remaster (CoD4 feel + menus/HUD + optional local AI HD textures/audio). Update `AGENTS.md`, root `README.md`, and `docs/plan.md` goal text accordingly.
- **Rationale:** Movement remains the gameplay core; HD packs and UI are first-class remaster deliverables, still non-redistributable when derived from proprietary assets.

## 2026-10-11: HD audio locked — sr_only + music sr_linked

- **Context:** Pilot A/B: denoise/enhance dulled VO; stereo AudioSR haze; mid-only OK; same-seed L/R (`sr_linked`) preferred for music.
- **Decision:** Lock `CURRENT_RECIPE=sr_only` and `CURRENT_MUSIC_MODE=sr_linked`. Full pack via `tools/hd-audio/remaster.sh` (batch `--resume` + pack → `codmod_hd_audio.pk3`). Pin `s_useOpenAL 1`.
- **Rationale:** Matches listen tests; resume survives overnight runs; OpenAL plays native 48 kHz from the override pk3.

## 2026-10-11: HD audio AudioSR on 8GB via VAE/UNet staging

- **Context:** AudioSR `torch.load(..., map_location=cuda)` OOMed on an RTX 4070 Laptop (8GB); an early heuristic then forced CPU, which is too slow for a full SP remaster.
- **Decision:** In `tools/hd-audio`, load checkpoints on CPU, move to CUDA, and run a staged `generate_batch` that keeps only VAE or UNet on GPU at a time; chunk long clips (~5s). No CPU fallback for remasters. Ship script only; `codmod_hd_audio.pk3` stays gitignored.
- **Rationale:** Staging peaks ~6GB and finishes short SFX in seconds on CUDA. Full half-precision of AudioSR breaks timestep dtypes; CPU-only is unacceptable for ~1360 files.

## 2026-10-11: Remove blank Sound Quality (`s_khz`) menu row

- **Context:** Codmod sound menus still exposed `s_khz` (11/22 kHz); iortcw has no such cvar, so the MULTI field painted blank.
- **Decision:** Delete the Sound Quality row (and its Apply) from `sound.menu` / `ingame_sound.menu`. Do not rewire to `s_sdlSpeed` in v1.
- **Rationale:** Dead control under OpenAL; an 11/22 toggle is misleading next to a 48 kHz remaster pack.

## 2026-10-11: Hub OPTIONS→GRAPHICS; SOUND + GAME sibling pages

- **Context:** After DISPLAY/QUALITY/EFFECTS landed, user wanted OPTIONS renamed and SOUND/VIEW out of that menu; VIEW still exposed vanilla crosshair size/preview and `cg_viewsize`.
- **Decision:** Rename hub OPTIONS to GRAPHICS; add hub SOUND + GAME (`sound.menu`/`game.menu` + ingame_*); override `ui/ingame.txt` to load them. Rename VIEW→GAME. Drop Crosshair Size/Alpha/preview and Screen Size; keep FOV, HUD alpha, cursor hints, brightness.
- **Rationale:** CoD procedural crosshair ignores `cg_crosshairsize`; UI_CROSSHAIR preview is misleading; letterboxing via `cg_viewsize` is a footgun. Sibling hub pages match CoD settings layout better than nested tabs.

## 2026-10-11: Options graphics split into DISPLAY / QUALITY / EFFECTS

- **Context:** VIDEO had too many rows once rend2 defaults (SSAO, MSAA, AF, sun shadows, …) needed menu exposure; user asked for scroll like mods but listbox scrollbars only feed text lists.
- **Decision:** Replace VIDEO with left tabs DISPLAY / QUALITY / EFFECTS (SOUND/VIEW shifted down). Cull NV fog, ATI Truform, GL Extensions, color depth, vertex lighting, texture bits, r_finish. Expose rend2 pack cvars; keep Apply on all three tabs. Do not expose `cl_renderer`, `r_dlightMode`, bloom/PBR/parallax/cubemaps.
- **Rationale:** Subtabs match LOOK/MOVE/SHOOT and need no UI C; listbox scroll cannot host yesno/multi rows.

## 2026-10-09: Menu hover hints use a fixed bottom strip

- **Context:** After CoD vertical layouts, `yesno_message` still sat at vanilla mid-screen (~y=320) over the value panel; `keyBindStatus` at the bottom clipped long text; `slider_message` was missing.
- **Decision:** Put all hover hints in one bottom strip (`controls`/`ingame_controls`: `rect 40 455 560 20`; `setup` messages: `rect 90 452 530 22`). Drop `keyBindStatus`’s `text " "` so `UI_KEYBINDSTATUS` paints at `rect.x`. Restore `slider_message` and add missing `message_modsoptions`.
- **Rationale:** Ownerdraw with a non-empty `text` + center `textalignx` offset the status string far right past 640; mid-screen rects were for the old horizontal controls layout.

## 2026-10-09: Merge System+Game Options; pause BACK reopens hub; sliders→EDITFIELD

- **Context:** Pause BACK closed the whole pause menu; hubs had separate SYSTEM and GAME OPTIONS; user wanted decimal number boxes instead of sliders.
- **Decision:** (1) Pause pages use `close … ; open ingame` on BACK/Esc. (2) Absorb system sections into `options_menu` / `ingame_options` (tabs GRAPHICS→SOUND→DRIVER→PERFORMANCE→VIEW); hubs expose one OPTIONS; `system_menu` / `ingame_system` become redirect stubs. (3) Replace every `ITEM_TYPE_SLIDER` with `ITEM_TYPE_EDITFIELD` + `cvar`/`maxChars` (not NUMERICFIELD).
- **Rationale:** Close does not restore UI focus so null focus unpauses; stubs keep vanilla load lists from resurrecting old menus; EDITFIELD accepts decimals without engine changes.

## 2026-10-09: Settings pages share setup chrome + own mods.menu

- **Context:** After option-B fullscreen value pages shipped, Main OPTIONS skipped the hub, submenus had no BACK/art, and MODS still used the vanilla dialog from `sp_pak3`.
- **Decision:** Main OPTIONS opens `setup_menu` only; value pages (and a new `ui/mods.menu` override) use setup-style `menu_select`/flame/BLACKGRAD chrome plus a CoD BACK row; mods keeps `FEEDER_MODS` + `uiScript loadMods`/`RunMod`.
- **Rationale:** Hub-first navigation matches CoD; shared art makes pages feel like the rest of the menu stack; mods only needed a `.menu` override, not C changes.

## 2026-10-09: Settings value menus as CoD fullscreen pages (option B)

- **Context:** After hub lists went vertical at x=40, vanilla `system`/`options`/`controls` (+ ingame_*) dialogs at `rect 100 125` still drew section tabs and value rows on top of hub labels.
- **Decision:** Rewrite those six menus as fullscreen pages: left CoD section tabs (`GRAPHICS`/`LOOK`/… at x=40), right value column at x=240, opaque backdrop. Opening from setup closes `setup_menu`; Esc reopens it. Pause settings stay fullscreen over `ingame` and Esc only closes the settings page.
- **Rationale:** Option B matches the main/pause list language and removes overlap without keeping two competing left stacks visible at once.

## 2026-10-09: Fullscreen toggles in-place (no vid_restart) on Wayland/MangoHud

- **Context:** Clicking Fullscreen → Apply (or `+toggle r_fullscreen +vid_restart`) under `game_run.sh` (gamemode + MangoHud, SDL Wayland) SIGSEGV'd during GL context recreate after `RE_Shutdown`.
- **Decision:** Handle fullscreen-only applies with `SDL_SetWindowFullscreen` (`FULLSCREEN_DESKTOP` on Wayland) in `IN_ToggleFullscreenInPlace` and `GLimp_EndFrame`; never fall back to `vid_restart` for FS-only. Peek pending latches with `Cvar_LatchedPending` / `Cvar_VariableLatchedInteger` instead of `Cvar_Get` (which applies latches).
- **Rationale:** MangoHud's GL intercept crashes when the context is destroyed/recreated for a FS toggle; in-place SDL toggle keeps the context. Rejected keeping the size-change→`vid_restart` fallback because that path is what segfaulted.

## 2026-10-09: E14 video modes via expanded tables + `r_availableModes`

- **Context:** Video Mode click-cycle missed common high-DPI sizes (1440p/4K); 2560×1600 was already mode 29 but buried; user wanted all display-available resolutions selectable.
- **Decision:** Extend `r_vidModes` in UI + opengl1 + rend2 through mode 41; rebuild the `r_mode` multi from SDL `r_availableModes` when set (else full table), always ending with Automatic/Custom.
- **Rationale:** `.menu` cvarFloatList is overwritten by `Item_ApplyHacks`; matching the three C tables keeps `R_GetModeInfo` aligned; filtering by detected modes shortens the cycle list to what the display actually offers.

## 2026-10-09: CoD-style pause menu in same `codmod_menus.pk3`

- **Context:** After the title-screen vertical list shipped, the user wanted the in-game ESC pause bar (`ui/ingame.menu`) matched.
- **Decision:** Override `ui/ingame.menu` in the same pk3: left stack SAVE/LOAD/CONTROLS/OPTIONS/SYSTEM/EXIT at x=40; keep top flame/logo chrome; give SAVE/LOAD unique item names for hover tint.
- **Rationale:** Same layout language as `main.menu`; no C changes; submenus stay vanilla.

## 2026-10-09: CoD-style main menu via `codmod_menus.pk3`

- **Context:** Vanilla RTCW title screen uses a horizontal bottom bar; user wanted a CoD-style vertical list (including Multiplayer) without C/engine work yet.
- **Decision:** Override `ui/main.menu` in `codmod_menus.pk3` (not `zz_*`): left vertical stack at x=40, hide bottom WOLFICON / gold lines / BLACKGRAD2; keep scene art and all six actions.
- **Rationale:** Same fs_game pk3 override pattern as `codmod_hud.pk3`; layout-only first slice before pause menu or new art.

## 2026-10-09: Default `r_gamma 3`

- **Context:** User’s playtest brightness (`r_gamma 3` in wolfconfig) should be the mod default, not engine 1.
- **Decision:** `seta r_gamma "3"` in `mod/codmod/codmod.cfg`.
- **Rationale:** Matches the locked in-game feel; archived every launch with other graphics defaults.

## 2026-10-09: Hip crosshair on Garand + scoped Mauser

- **Context:** Vanilla hid Garand entirely from `CG_DrawCrosshair` and hid Mauser when `WP_SNIPERRIFLE` was owned — looked like “some weapons have no crosshair.”
- **Decision:** Remove those early-outs; scoped alts still use `CG_DrawWeapReticle`.
- **Rationale:** CoD-like hipfire needs a reticle on every firearm until/unless we decide otherwise.

## 2026-10-09: ADS per-weapon absolute bake + tune log

- **Context:** Deferred Phase 3 needed a walk of all 9 iron-sight weapons; global iron-sight cvars were Luger-centric and fought per-weapon table biases during live tune.
- **Decision:** While `cod_adsTune` is on, the selected weapon’s `cg_codAdsView` row is an absolute pose (globals folded once). `cod_adsTuneSave` appends to `codmod_ads_tune.log`; bake writes absolute rows and zeros global iron-sight defaults; then `cod_adsCrosshair 2`.
- **Rationale:** Absolute-per-weapon avoids mid-session cross-talk and makes the log the single source for bake. Globals remain an optional master offset after bake (default 0).

## 2026-10-09: Prone crawl `cod_proneScale 0.55`

- **Context:** CoD4 default 0.15 (30 u/s) felt unusably slow in RTCW playtest; 0.4 still felt slow.
- **Decision:** Default `cod_proneScale` to **0.55** (~110 u/s at jog 200); still under crouch 130.
- **Rationale:** User locked the value after live `/set` tuning. Keep CoD “slower than crouch” without the crawl feeling stuck.

## 2026-10-09: Uncap FPS via cfg only (`com_maxfps 0`)

- **Context:** Engine default `com_maxfps` is 76; user wanted uncapped FPS for everyone without engine churn.
- **Decision:** `seta com_maxfps "0"` in `mod/codmod/codmod.cfg` only (exec’d every launch). No `common.c` change.
- **Rationale:** Engine already treats `com_maxfps <= 0` as no sleep cap (`minMsec = 1`, ~1000 soft ceiling). Cfg keeps `--vanilla` at 76 and avoids an upstream-hostile engine patch.

## 2026-10-09: Enable remaining working rend2 graphics defaults

- **Context:** User wanted every non-broken rend2 feature on (after SSAO + forward dlights), MSAA at 2×, and specular mapping.
- **Decision:** Default in `codmod.cfg` + latch `+set`s in `run.sh`: MSAA 2, AF 16, float lightmaps, specular/deluxe mapping, `r_forceSun 1`, sun rays, soft hi-res cascades (filter 2 / 2048), keep HDR/tonemap/autoExposure. Explicitly leave off dlightMode 2, bloom, PBR, cubemaps, imageUpsample, genNormalMaps, sunlightMode 2, parallax/normals pack.
- **Rationale:** Stock skies have `q3map_sun` but not `q3gl2_sun`, so `r_forceSun` is what actually arms CSMs. Specular mapping is on and auto-loads `*_s`, but we ship no specular pack yet — surfaces use `r_baseSpecular` until maps exist.

## 2026-10-09: Flashlight as rend2 eye-origin spot cones

- **Context:** Point-dlight chain (esp. impact light on the aimed wall) made each looked-at surface brighten like its own texture blob. User liked `r_dlightMode 1` but not that look.
- **Decision:** Add `RE_AddSpotLightToScene` (REF_API 9 / `CG_R_ADDSPOTLIGHTTOSCENE`); rend2 GLSL applies cone attenuation in ForwardDlight + ProjectDlight. Flashlight = two eye-origin spots (16° hot / 28° fill), no wall impact lights. Default `r_dlightMode 1` in `codmod.cfg` + `run.sh`.
- **Rationale:** Real cone from the eye lights facing geometry with N·L instead of planting a sphere on the hit surface. Skipped CG_Spotlight overlay (already rejected as too fake).

## 2026-10-09: HD fonts locked to general-wdn 4×

- **Context:** A/B’d UltraSharp 4× (weird) and animevideov3 4× (unsure); user preferred general-wdn at native 4× for glyph atlases.
- **Decision:** Font path is `--font-model general-wdn --font-scale 4`; world stays `general-wdn` 2×. README credits [`realesr-general-wdn-x4v3`](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth) / [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN).
- **Rationale:** Same WDN weights at true 4× looked best on UI text in-game.

## 2026-10-09: HD fonts via animevideov3 4× (not UltraSharp)

- **Context:** Dual-model batch shipped fonts through UltraSharp 4×; in-game the glyphs looked weird.
- **Decision:** Font path is `--font-model animevideov3 --font-scale 4`; world textures stay `general-wdn` 2×. Dual-model/`--only-fonts`/`pack --merge` unchanged.
- **Rationale:** animevideov3 is cleaner on painted/game art; UltraSharp over-sharpened or distorted the glyph atlases. Superseded same day by general-wdn 4×.

## 2026-10-09: HD fonts via UltraSharp 4× (dual-model batch)

- **Context:** UI text looked blurry because `codmod_hd.pk3` AI-upscaled glyph atlases with the same `general-wdn` 2× path as world textures.
- **Decision:** `hd-textures batch` routes `fonts/**` and `menu/art/font*` through `--font-model ultrasharp --font-scale 4`; everything else stays `general-wdn` 2×. Font-only refresh uses `--only-fonts` + `pack --merge`.
- **Rationale:** Photo upscalers soften tiny glyphs; UltraSharp at native 4× targets sharp game UI. Glyph `.dat` files stay vanilla (normalized UVs). Superseded the same day by animevideov3 after playtest.

## 2026-10-09: Default rend2 SSAO on (`r_ssao 1`)

- **Context:** User playtested ioRTCW rend2 screen-space AO and found `r_ssao 1` looks great.
- **Decision:** Default `r_ssao 1` in `mod/codmod/codmod.cfg` and early `+set` in `scripts/run.sh` (CVAR_LATCH, same pattern as `cl_renderer`).
- **Rationale:** No engine work; stock rend2 SSAO; latch early so first boot actually enables it.

## 2026-10-09: Drop baked normal/POM pack after A/B

- **Context:** User compared with `r_normalMapping 0` and preferred the look without the offline `_n` pack.
- **Decision:** Delete `codmod_pom.pk3`, `tools/pom-bake`, and `mod/codmod/scripts/codmod_pom.*`; keep rend2/SSAO, flashlight flat brightness, and 2560×1600/UI mode-list fixes.
- **Rationale:** Luma-from-diffuse normals were not useful enough to keep the asset/tooling cost.

## 2026-10-09: SP-wide normals (`_n`) for floors/walls + weapons; POM off

- **Context:** User wanted normals for the rest of the game floors/walls and weapons after the escape1 POM floating issue.
- **Decision:** Bake rend2 `*_n.png` for ~800 SP surface textures (BSP + wall/floor dirs) and weapon body maps; world uses auto `_n` discovery; weapons get `codmod_pom.mtr` with `rgbGen vertexLit` + `normalmap`; keep `r_parallaxMapping 0`.
- **Rationale:** Normals give depth without sinking floors; one shader name can’t differ by brush orientation, so POM stays off for the full pack.

## 2026-10-09: Floor-shared materials → normals only (no POM)

- **Context:** After strengthening escape1 POM, props looked like they floated off floors (and sometimes walls). Many `castle_wall` shaders are also used on floors/steps in the BSP.
- **Decision:** Keep bump via `stage normalmap` on floor-shared textures; reserve `normalparallaxmap` for wall-dominant leftovers; set `r_parallaxMapOffset 0.5` so height is centered (default 0 only recesses).
- **Rationale:** One shader name can’t differ by brush orientation; POM always sinks the visible surface relative to collision, so floors with POM guarantee floating props.

## 2026-10-09: Wall POM smoke test via rend2 + offline `_nh` bake

- **Context:** Want more realistic wall depth on escape1; ioRTCW rend2 already has normal maps + POM; classic opengl1 does not. User chose offline bake from HD diffuse over `r_genNormalMaps` for the first look test.
- **Decision:** Add `tools/pom-bake` (luma height + Sobel normals → `*_nh.png`), pack local `codmod_pom.pk3` with `scripts/codmod_pom.mtr` (+ stub `.shader` for discovery) for three `castle_wall` textures; default codmod to `cl_renderer rend2` and `r_parallaxMapping 1` (cfg + `run.sh` early `+set` because both are `CVAR_LATCH`).
- **Rationale:** No engine feature work; baked `_nh` is swappable later; `.mtr` keeps opengl1 from parsing advanced stages; early `+set` makes the first boot actually use rend2/POM.

## 2026-10-09: HD textures — switch to general-wdn 2×

- **Context:** Cascaded ani4k 4× still looked almost unnoticeable in-game; user preferred trying RealESRGAN general-wdn at native-style 2× instead.
- **Decision:** Replace `codmod_hd.pk3` with full SP `general-wdn` at `--scale 2` (JPEG 90).
- **Rationale:** Pilot showed general-wdn sharper/more detailed than ani4k; sticking to 2× keeps VRAM/pk3 size sane while changing the reconstruction look.

## 2026-10-09: HD textures — bump to 4× cascaded ani4k

- **Context:** After the 2× pack, escape1 walls still looked soft on a high-res display; full ani4k batch was fast enough to try higher scale.
- **Decision:** Re-run full SP with `--scale 4` (native-2× ani4k applied twice). Keep JPEG 90; replace local `codmod_hd.pk3`.
- **Rationale:** 256²→1024² / 512²→2048² matches modern screens better than 2×; cascading reuses the chosen model without switching to slower 4× nets. (Superseded the same day by general-wdn 2×.)

## 2026-10-09: HD textures — ani4k for first full SP pack

- **Context:** Pilot compared x2plus / general-wdn / animevideov3 / ultrasharp / local Ani4K Compact; user said ani4k looks okay and wanted a full run.
- **Decision:** First full SP pack uses `ani4k` (`~/Models/2x_Ani4K_Compact_35000.pth`) at 2× with JPEG quality 90; output is local `codmod_hd.pk3` only. `codmod.cfg` sets `r_picmip`/`r_picmip2` to 0.
- **Rationale:** Fastest warmed model on the 4070 (~79 ms for 512²→1024²) with acceptable look; quality/JPEG can be revisited without changing the pipeline.

## 2026-10-09: HD textures — shareable script, local pk3, worktree

- **Context:** Want 2× AI upscales for full SP story textures without blocking gameplay work on `main`, and without redistributing proprietary id art.
- **Decision:** Implement on branch/worktree `hd-textures` (`../rtcw-cod-hd-textures`). Ship only `tools/hd-textures` (uv + CUDA torch); gitignore `samples/`, `.cache/`, `codmod_hd.pk3`. Pilot requires CUDA and prints the GPU banner; full batch only after a model/JPEG pick.
- **Rationale:** Sibling worktree keeps Phase 5d/6 free; regenerable local outputs match the ET-anims pattern; silent CPU fallback would poison timing comparisons.

## 2026-10-09: Flashlight lighting-only + HUD icon; drop spotlight overlay

- **Context:** Spotlight cone/core looked too strong; close walls went dark; weapon icon was squashed in the CoD HUD slot.
- **Decision:** Remove `CG_Spotlight` overlay; keep forced dlights with `cod_flashlightMinDist` linear 55%→100% closeScale; HUD on-indicator beside weapon icon; draw weapon icons at native 1:1 / 2:1 aspect. Default intensity 500.
- **Rationale:** Lighting carries the gameplay cue; a HUD icon is clearer than a world beam. Native icon aspect fixes half-width-in-square-slot squash.

## 2026-10-09: ResampleTexture allocates p1/p2 by outwidth (HD pack)

- **Context:** `./scripts/run.sh codmod +spdevmap escape1` SIGSEGV'd during client init with `codmod_hd.pk3` (2048+ TGAs). Without the HD pk3, the map loaded.
- **Decision:** Replace fixed `p1[1024]`/`p2[1024]` (opengl1) and `p1[2048]`/`p2[2048]` (rend2) with `Hunk_AllocateTempMemory(outwidth * …)` + matching free in both SP `ResampleTexture`s. Rebuild/install renderer `.so`s (not game-only).
- **Rationale:** Index buffers are sized to output width; HD downscales past the old stack caps and smash the stack. Hunk temp matches other image paths in the same file. (Engine change still uncommitted as of this flashlight commit.)

## 2026-10-09: Save load ignores cameraPortal; flashlight uses CG_Spotlight

- **Context:** Loading escape1 save `daniel` SIGSEGV'd in `ClientThink_real` → `G_SetOrigin` with a garbage `client->cameraPortal`. Flashlight was two omnidirectional dlights and looked weak.
- **Decision:** Put `cameraPortal` / `persistantPowerup` in `gclientIgnoreFields`, null them after `ReadClient`, and bounds-check before use. Flashlight draws `CG_Spotlight` with new `SL_NOMODEL` plus forced dlights along the view ray.
- **Rationale:** Those pointers were never `F_ENTITY`-serialized, so old saves store raw addresses; cutscene cameras should not survive load anyway. Reusing the engine spotlight gives a real cone/core/impact without inventing a new beam renderer.

## 2026-10-09: Phase 6 — sprint+crouch slide; fire allowed, ADS blocked

- **Context:** CoD tactical slide needs networked, predictable state and a clean crouch hand-off after linear speed decay. Player must be able to shoot mid-slide like modern CoD.
- **Decision:** `PMF_COD_SLIDING` (bit 128) + `STAT_COD_SLIDE` (ms left / negative cooldown) + `STAT_COD_SLIDE_SPEED` (start speed for decay). Start on sprint + crouch-press edge while standing and ≥ `cod_slideMinSpeed`. No friction/accel; limited `cod_slideSteer`. Fire works (sprint cleared on start); ADS blocked unless `cod_slideAllowADS 1`.
- **Rationale:** Networked stats keep prediction stable; forcing `PMF_DUCKED` for the whole slide matches CoD crouch bbox and unlocks crouch-only gaps; blocking ADS avoids fighting iron-sight raise during a short slide.

## 2026-10-09: Phase 5d — full bind reset, toggle crouch, flashlight

- **Context:** New binds (ADS, quickknife) were easy to miss; `--reset-binds` only overlaid a few lines. Crouch was hold; RTCW has no player flashlight; empty-clip reload could skip the FP anim after the fire-anim timer lock.
- **Decision:** `codmod_binds.cfg` does `unbindall` → `default.cfg` → codmod deltas; same path from `--reset-binds`, menu Defaults (codmod), `/cod_resetbinds`. Default `C` = `togglecrouch` (auto-stand on SPACE). `L` = `toggleflashlight` (client dlight). Packs clamp to `cod_maxHealth`. Reload always `PM_StartWeaponAnim(WEAP_RELOAD1)`.
- **Rationale:** One complete reset file is the durable fix for “missing new binds”; toggle crouch matches CoD and keeps slide’s `upmove < 0` trigger; flashlight is greenfield because SP has no remnant.

## 2026-10-09: CoD hipfire floor + click-fire for non-autos

- **Context:** Hipfire was near-laser when standing still (`aimSpreadScale` decays to 0). Holding fire also sprayed pistols/bolt/semi at their `nextShotTime`, unlike CoD.
- **Decision:** `BG_CodFireSpreadScale` floors hip `aimSpreadScale` at `cod_hipSpreadMin` (0.55) and lerps to ADS-tightened spread; `cod_semiAutoClick` + `BG_CodNeedsClickFire` require `releasedFire` between shots for pistols/akimbo/mauser/garand/sniper/panzer. Automática (MP40/Thompson/Sten/FG42/Venom/flame) unchanged.
- **Rationale:** One FireWeapon path keeps bullet cone and crosshair aligned; `releasedFire` already existed for pistol tap — generalize it instead of a new button edge bit.

## 2026-10-09: SP hit markers via PERS_HITS + PERS_GAUNTLET_FRAG_COUNT for headshots

- **Context:** E9 wants a CoD X flash and distinct body/headshot ticks. Vanilla only increments `PERS_HITS` in MP, so SP never got hit beeps. `MAX_PERSISTANT` is full (16).
- **Decision:** In SP `G_Damage`, when the player damages a living AI, increment `PERS_HITS`; on headshot also increment `PERS_GAUNTLET_FRAG_COUNT` (MP-only reward counter, unused in SP). Cgame watches both deltas for marker + sound.
- **Rationale:** No new networked fields; headshot vs body is one extra unused persistant; prediction-safe because it rides existing `playerState_t.persistant[]`.

## 2026-10-09: CoD 4-post crosshair; ADS keeps center dot for now

- **Context:** After Phase 5c HUD confirm, user wants Call of Duty reticle behaviour: four posts, gap bloom from move/fire, ADS removes the 2D posts. Per-weapon iron sights are not finished, so a full ADS hide would leave no aim cue.
- **Decision:** Procedural `CG_CodDrawCrosshair` (`cod_crosshairStyle 1`): posts bloom with `aimSpreadScale` + XY speed; ADS fades posts; center dot stays while `cod_adsCrosshair 1`. Mode `2` still hides everything once all weapons are tuned.
- **Rationale:** Matches CoD visual language without requiring new shaders; keeps the interim ADS aid from Phase 3 until the deferred per-weapon bake.

## 2026-10-08: Phase 5c heat/health as colour ramps, not bars

- **Context:** User rejected dropping MG heat with no replacement; wants ammo text white→yellow→orange→red for overheat, and the same ramp on the crosshair for health. Stamina must keep Phase 5b feel with no bar.
- **Decision:** Shared `CG_CodThreatColor` ramp: heat → ammo text (`curWeapHeat`); missing health → crosshair/ADS dot (replace vanilla `CG_ColorForHealth` when `cod_hudEnable`). No heat bar. Stamina gameplay unchanged.
- **Rationale:** One visual language for “getting worse”; bars are non-CoD. Vanilla crosshair health assumes ~100 HP and a different palette.

## 2026-10-08: Phase 5c CoD HUD before slide (after vitals)

- **Context:** After Phase 5b bars, user wants a CoD-like on-screen HUD: BO Zombies-style `clip/reserve` ammo, no stamina/health bars, bloody screen at low health — before tactical slide.
- **Decision:** Insert Phase 5c ([phase-5c-hud.md](../docs/phase-5c-hud.md)) between 5b and 6. Presentation via `cod_hudEnable` + `hud.menu` / cgame draws; vitals gameplay stays on `cod_vitalsEnable`. Low-HP feedback is a persistent blood/vignette layered on existing hit blood.
- **Rationale:** Bars were an interim read; CoD communicates health through screen feedback and ammo as one corner number. Doing HUD before slide avoids re-tuning chrome mid-movement work.

## 2026-10-08: Player ammo via `cod_ammoScale` in Add_Ammo (not ammoTable)

- **Context:** User wants ~2× starting and found ammo without buffing AI.
- **Decision:** Scale count and max carry in `Add_Ammo` / `BG_CodMaxAmmo` when the recipient is the player; leave `ammoTable` untouched.
- **Rationale:** `ammoTable` is shared with AI; mutating it would give soldiers more ammo too.

## 2026-10-08: Never name mod pak files `zz_*`

- **Context:** `zz_codmod_hud.pk3` never loaded; stamina stayed vertical and health used the vanilla square number rect.
- **Decision:** Ship HUD as `codmod_hud.pk3` (copy into `run/codmod/`, not a `zz_*` name).
- **Rationale:** ioRTCW `FS_AddGameDirectory` rewrites basenames starting with `zz_` to `sp_` before opening the file (SP pak sort hack), so `zz_codmod_hud.pk3` looks for a non-existent `sp_codmod_hud.pk3`.

## 2026-10-08: Phase 5b is health/stamina/vital HUD before slide

- **Context:** After quickknife, user wants CoD auto health regen, CoD-like stamina (RTCW already close), and horizontal health + stamina bars instead of a health number + vertical stamina.
- **Decision:** Insert Phase 5b ([phase-5b-vitals.md](../docs/phase-5b-vitals.md)) before slide (6). Regen via last-damage delay + rate tick; finish stamina by removing vanilla multi-tier recharge and adding a short recharge delay; override `ui/hud.menu` in a mod pk3 for horizontal bars.
- **Rationale:** Survivability and exertion HUD are CoD baseline feel; doing them before slide keeps slide playtests readable on the new vitals.

## 2026-10-08: Quickknife snappiness via `cod_knifeSwitchTime` + early return

- **Context:** Quickknife worked but felt disconnected — 250 ms knife drop/raise and waiting for knife READY before return.
- **Decision:** `cod_knifeSwitchTime` default 75 ms for player knife in/out; cgame returns as soon as the swing registers (`WEAPON_FIRING` / `weaponTime > 0`).
- **Rationale:** Ties the V press to the visible swing without chopping the raise anim entirely; still tunable.

## 2026-10-08: `/cod_menu` text size via `cod_menuScale`

- **Context:** The tune overlay used full `SMALLCHAR` (8×16) and filled most of the 480-tall virtual screen.
- **Decision:** Add archived `cod_menuScale` (default 0.7, clamp 0.5–1.0), expose it in a top **MENU UI** section, and derive char size / panel width / visible rows from it with a 400px height cap.
- **Rationale:** Shrinks the default footprint while letting the user retune live; `CVAR_ARCHIVE` matches other UI prefs like `cod_debugHud`.

## 2026-10-08: Quick knife is cgame `quickknife` on V (not +kick)

- **Context:** User wants CoD-style press-V knife then return to previous weapon. RTCW has no separate melee mode — only `WP_KNIFE` plus unrelated foot `+kick`.
- **Decision:** Cgame command `quickknife` bound to `V`: save previous weapon, `CG_FinishWeaponChange` to knife, auto one attack when READY, switch back. Dedicated prev-weapon slot (not `cg.switchbackWeapon`). Do not bind V to `+kick`.
- **Rationale:** Matches existing scope-hold / toggleads patterns; no new networked pmove state; SP has no cfg `alias` chains.

## 2026-10-08: Phase 5 is feel (jump/inertia + pistol fire rate); slide becomes 6

- **Context:** After gait confirm, pistols still felt locked (~400 ms nextShotTime in SP) vs CoD click-fire; jump/gravity/ground inertia were still Quake-vanilla.
- **Decision:** Insert Phase 5 ([phase-5-feel.md](../docs/phase-5-feel.md)): pistol tap-fire + min interval, `cod_jumpVelocity`/`cod_gravity`, player-only accel/friction, landing slowdown. Renumber slide→6, prone→6b, extras→7. Promote E6/E7/E17/E18 out of optional extras.
- **Rationale:** Ties movement and trigger response to player input before adding new moves (slide).

## 2026-10-08: Phase 4 is gait presentation; slide becomes 5

- **Context:** Phase 2 only retuned speeds; FP still feels like Quake jog because RTCW has no walk/run/sprint viewmodel anims and sprint shared jog bob/pose. User wanted body/weapon gait feel before slide/prone.
- **Decision:** Insert Phase 4 (gait): procedural sprint gun-lower, gait-scaled bob, sprint camera; fire while sprinting cancels sprint and shoots same frame (no fire-block). Renumber slide→5, prone→5b, extras→6. Promote former E1 into Phase 4 with the modified fire rule.
- **Rationale:** Biggest CoD “I’m walking vs running” read is FP presentation; new skeletal anims are out of scope.

## 2026-10-08: Gate Phase 3 on Luger; defer per-weapon ADS tune

- **Context:** Luger/pistol ADS feels good enough to move on; walking every firearm's iron-sight params would block Phase 4.
- **Decision:** Accept Phase 3 core for the Luger now and start Phase 4 (slide). Keep a hard open item for a full per-weapon ADS parameter review/bake; do not set `cod_adsCrosshair 2` (hide dot) until that pass is done.
- **Rationale:** Unblocks slide work without losing the important multi-weapon tune; the interim center-dot crosshair stays until sights are reviewed per weapon.

## 2026-10-08: ADS crosshair is a center dot (hide later)

- **Context:** hip crosshair over iron sights looks wrong; full hide was too early while only the Luger is tuned.
- **Decision:** `cod_adsCrosshair 1` draws a 2×2 center dot while ADS (`e > 0.5`); mode `2` will hide it once all ADS weapons are tuned.
- **Rationale:** keeps an aim reference during the multi-weapon tune pass without the full hip reticle.

## 2026-10-08: `+ads` registered in engine (RTCW has no `alias`)

- **Context:** Phase 3 cfg used Quake-style `alias +ads "+wbutton6"`, but ioRTCW SP has no `alias` console command (`Unknown command alias` / `Unknown command +ads` in smoke logs).
- **Decision:** register `+ads`/`-ads` in `cl_input.c` as the same handlers as `+wbutton6`/`-wbutton6`, bind `MOUSE2` to `+ads`, and provide cgame `toggleads` for sticky aim. No cfg aliases.
- **Rationale:** keeps the intended `+ads` name and hold/toggle UX without inventing a fake alias system.

## 2026-10-08: `cod_enable` defaults to 1

- **Context:** Phase 2 wiring initially defaulted `cod_enable` to 0, which would make `scripts/run.sh` feel like vanilla until the user typed a console command.
- **Decision:** default `cod_enable` to 1 in `bg_cod.c` and mirror it in `mod/codmod/codmod.cfg`. `cod_enable 0` remains the instant A/B back to vanilla.
- **Rationale:** the mod should be active out of the box when `fs_game` is `codmod`.

## 2026-10-08: Post-core UI polish parked as E14–E16

- **Context:** user asked for higher in-game resolutions (e.g. 2560×1600), a numeric mouse-sensitivity field, and an FOV slider, after the last planned phase.
- **Decision:** add them as phase-5 extras E14–E16; do not start them until phases 1→4b (tier A) are done, unless the user asks earlier.
- **Rationale:** keep the movement/gunplay phase order intact; these are menu/UI polish, not movement.

## 2026-10-08: Design decisions D1-D10 live in docs/plan.md

- **Context:** the planning phase made ten decisions (build environment, prone, ADS input, scoped weapons, speeds, `g_speed`, lean-fire, naming, AI speeds, prone animations).
- **Decision:** keep them in `docs/plan.md` section 6 rather than duplicating here. Add new decisions to this file, newest first, and update that table only if one of D1-D10 is reversed.
- **Rationale:** one source of truth for the original ten; this log covers everything decided during implementation.
