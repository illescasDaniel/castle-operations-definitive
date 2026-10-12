# Progress

Open items first. Finished work moves to `archive.md`. Phase details live in `docs/plan.md` (section 7 mirrors this list).

## RTCW remaster (`codmod`) — CoD4 feel + HD presentation

### Done
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
- [ ] Phase L0 (optional): translate menus and available game data (briefings, strings, codmod menus/HUD) — see docs/phase-l10n.md
- [ ] Phase L1 (optional): AI-transcribe dialogue audio into subtitles + subtitle display
- [ ] Phase L2 (optional): AI-translate subtitles
- [x] README "Localization (community patches)" section with German/Spanish packs — 2026-10-12
- [x] First-launch defaults: triple buffer, no cap, desktop res, fullscreen; docs/menus.md rules — 2026-10-12
- [x] GRAPHICS > ADVANCED tab + `codmod_gfxdefaults.cfg` (settings persist now) — 2026-10-12, awaiting in-game check
- [x] GRAPHICS menu trimmed to one page (AA, VSync, FPS limit, mode, fullscreen, brightness); pk3 repacked — 2026-10-12, awaiting in-game check of main + pause menus
- [x] Phase 5b: health regen, CoD-like stamina, horizontal health/stamina bars (confirmed 2026-10-08)
- [x] Phase 5b follow-up: double ammo + interact hint (“Press F” / “Breakable”) (confirmed 2026-10-08)
- [x] **Phase 3 per-weapon ADS bake** — all 9 from `codmod_ads_tune.log` final pass (2026-10-09); globals 0; `cod_adsCrosshair 2`; `cod_adsCrosshairForce` for re-tune; tooling kept.
- [x] Hip crosshair on Garand + Mauser-with-scope (was vanilla-hidden) — 2026-10-09
- [x] Default `r_gamma 3` in `codmod.cfg` — 2026-10-09
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
- [ ] Phase 7: extras (optional)
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
- [x] **Frame-perfect FPS limiter + vsync modes:** all plan steps done 2026-10-12 (uncommitted iortcw + outer; awaiting user review/playtest incl. HUD + ESC pause). `Sys_WaitUntil`, pacer modes 0/1/2, `r_vsync` 0-4 (Off/On/Adaptive/Triple/Low latency), sub-ms cgame lerp, DISPLAY menu rows (menus pk3 repacked). Details + results: `docs/fps-limiter.md` section 6. Open: Windows untested; vsync 1-3 not validated on this Wayland box.
- [x] **HRTF 3D audio:** OpenAL Soft `ALC_SOFT_HRTF` via `s_alHRTF` (default on) + sound-menu row; effects volume 1.0. Playtested OK 2026-10-12. Ideas left: EFX reverb per area, low-pass occlusion.
- [x] **Kick buff + R3 tap/hold:** `cod_kickDamage` 50 (vanilla 15); pad R3 `+quickkick` = tap quickknife / hold kick. Playtested OK 2026-10-12. Docs: `phase-5-feel.md`.
- [x] **iortcw fork published:** all 83 engine paths on `illescasDaniel/iortcw` `cursor/codmod-patches-0f47` (+ `codmod` mirror) match local `git am` of `patches/`; PR https://github.com/illescasDaniel/iortcw/pull/1 (2026-10-12).
- [x] **Outer uses fork:** `setup.sh` clones `illescasDaniel/iortcw` branch `codmod` (no `git am`); `patches/` kept as `export-patches.sh` backup (2026-10-12).
