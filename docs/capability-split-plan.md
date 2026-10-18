# Plan: separate engine capability from codmod config

Status: Phase 1 implemented 2026-10-18 (uncommitted; menu layers in progress); awaiting user in-game check.

Goal (user, 2026-10-18):
1. The `iortcw` fork plays **vanilla RTCW by default** (original movement, HUD, look and sound), but exposes every
   codmod feature as a cvar so a mod can switch it on and tune it.
2. `mod/codmod/` turns everything on through config: movement, weapons, HUD, vitals, textures, audio, video,
   subtitles, input.

Background: `docs/architecture.md` section 0 ("Current coupling").

## 1. Audit summary (what is coupled today)

| Area | Today | Count |
|---|---|---|
| `bg_cod.c` table (`cod_*`) | `cod_enable 1` master switch plus ~20 per-feature `*Enable` flags, all on; ~170 tuning values with CoD numbers as code defaults | 195 cvars, 107 `bg_cod.enable` checks in 14 game/cgame files |
| Other `cod_*` (engine/cgame/ui) | `cod_subtitles 1`, `cod_skipIntro 0`, `cod_textLang`/`cod_audioLang en`, `cod_pad*` read by `cl_input.c`/`sdl_input.c` | ~12 |
| Renderer opinions on by default | `r_bloom 2`, `r_grade 1`, `r_ao 2`, `r_aa 3` (SMAA), `r_codSpecular 1`, `r_dlightEntities 1`, `r_flashlightShadow 1`, `r_cameraExposure 1.65` (upstream 1), `r_cutsceneFx 31` | ~10 |
| Renderer values pinned only by the mod | `r_deluxeSpecular 3`, `r_cubeMapping 1`, `r_forceSun`, `r_sunShadows`, `r_floatLightmap`, `r_dlightMode 1`, ... via `run.sh +set` and `codmod.cfg` | ~15 |
| Sound | `s_alHRTF 1` (new, upstream has no HRTF) | 1 |
| Hard-coded, no switch | intro always plays (ignores `com_introPlayed`), any key skips cinematics, cutscene letterbox change, menu cursor hotspot at top-left tip, 4:3 briefing with blurred backdrop, autosaves listed with manual saves | ~6 |
| Launch coupling | `run.sh` `+set`s ~16 latched renderer/input cvars and `+exec codmod.cfg`; first-launch `+exec codmod_binds.cfg`; the mod only works when started through `run.sh` | - |

Everything else in the fork is either a **capability** that does nothing unless used (gamepad/gyro, MJPEG cinematics,
extra video modes, multi-language tables, `+ads`/`+sprint` commands, `/cod_menu`, GPU profiler) or a **fix**
(see section 4) and stays as is.

## 2. Mechanism (how the mod switches things on)

**Engine: generic mod config hooks** in `Com_ExecuteCfg` (`qcommon/common.c`), no codmod name in the engine:

```
exec default.cfg                 (game's own, unchanged)
exec <fs_game>_defaults.cfg      NEW: mod defaults (first launch + Reset); before the user config, so saved choices win
exec wolfconfig.cfg              (user config)
exec autoexec.cfg                (user)
exec <fs_game>.cfg               NEW: mod pinned/internal config; after the user config, so it always applies
```

Only when `fs_game` is set and not `main`. This runs before renderer/input init, so latched cvars
(`r_cubeMapping`, `in_joystick`, ...) apply on the first boot without `run.sh +set`. It also runs again on
`fs_game` change (`Com_GameRestart`).

**Mod files** (`mod/codmod/`):

| File | Holds | Rule |
|---|---|---|
| `codmod_defaults.cfg` (new, replaces `codmod_gfxdefaults.cfg` and run.sh first-launch logic) | `seta` for every user-facing option (graphics menu, subtitles, language, pad sens, flashlight colour, volumes, `r_mode -2`, `r_fullscreen 1`) and `exec codmod_binds.cfg` | Saved wolfconfig values override it, so menu choices persist |
| `codmod.cfg` (exists) | `set` for every internal value: `cod_enable 1`, every `cod_*` feature flag and tuning value, pinned renderer cvars (`r_deluxeSpecular 3`, `r_cubeMapping 1`, ...), `cg_subMsecLerp` | Never a menu option (rule in AGENTS.md stays) |
| `codmod_binds.cfg` | Binds only, plus what the Reset action needs | Menu "Reset" execs `codmod_defaults.cfg` |

**Code defaults** become vanilla-safe. User-facing menu cvars keep `CVAR_ARCHIVE`; their engine default is now the
vanilla value and the mod's default comes from `codmod_defaults.cfg`. This changes the AGENTS.md "User settings vs
internal config" rule (code default -> mod defaults file); update AGENTS.md and `docs/menus.md`.

**Existing installs:** `Cvar_WriteVariables` writes every archived cvar, so the user's current `wolfconfig.cfg`
keeps today's values; non-archived `cod_*` come from `codmod.cfg`. Result: codmod should look and play identical.
We never edit `wolfconfig.cfg`.

## 2b. Menus in two layers (added 2026-10-18)

A capability nobody can switch on from a menu is of little use, so engine features get menu rows in the engine
layer, and the mod only adds its own design on top.

| Layer | Holds | Built as |
|---|---|---|
| Engine (`iortcw/SP/menus/deltas/`, in the fork) | Rows for engine features any player can use: AO/GTAO, AA, bloom, grade, specular, exposure, flashlight shadows, display mode, vsync, FPS limit, video modes popup, HRTF, pad on/sens/gyro, language, subtitles | Deltas on RTCW's menus -> menus pk3 for `main` |
| Mod (`menu-deltas/codmod/`) | `cod_*` gameplay rows (flashlight, aim assist, skip intro, ...), CoD-style main/pause/settings layout, cursor art | Deltas on the engine-layer result -> codmod menus pk3 |

In vanilla the engine rows show vanilla defaults (features off); codmod's defaults file turns them on. The 30 current
deltas mix both, so they are sorted into the two folders and `build-menus.sh` applies them in two passes. Deltas
and the script stay in the outer repo for now (RTCW menus are still never committed).

## 3. Default changes

### 3a. Game modules (`bg_cod.c` and friends)
- `cod_enable` default `0`. Audit all 14 files so **every** codmod path is behind `bg_cod.enable` (or its own
  flag): double ammo (`cod_ammoScale`), health clamp/`cod_maxHealth`, pistol 200 ms, toggle crouch, hit-marker
  `PERS_HITS`, interact hint, kick, quick knife, scripted-event AI speeds, reload/fire-anim changes that alter feel.
- Per-feature flags keep default `1` as sub-switches under the master (decision D2 below).
- Write the full current `cod_*` table into `codmod.cfg` (generated once by script from `bg_cod.c`), so the mod
  is the source of truth for every value it relies on. Code tuning defaults become the vanilla-equivalent value
  where one exists (lean 28/280/350, duck 100, jump 270, friction 6, accelerate 10, ammo scale 1, health 100, ...);
  others stay as inert fallbacks.
- `cod_subtitles` default `0` (mod default 1).

### 3b. Renderer (rend2)
`cl_renderer` engine default becomes `rend2` (`client/cl_main.c`); `cl_renderer` itself was removed
in section 9 (the engine always loads rend2). `cl_renderer` is removed from `run.sh` and `codmod.cfg`, and the opengl1 choice from the menus.

| Cvar | Engine default (new) | codmod sets |
|---|---|---|
| `r_bloom` / `r_grade` | 0 / 0 | 2 / 1 (defaults file) |
| `r_ao` | 0 | 2 (defaults file) |
| `r_aa` | 0 (upstream: no AA) | 3 SMAA (defaults file) |
| `r_codSpecular` (latched) | 0 | 1 (defaults file) |
| `r_dlightEntities`, `r_dlightSpecular` | 0 | 1 (pinned) |
| `r_flashlightShadow` | 0 | 1 (defaults file) |
| `r_cameraExposure` | 1 (upstream) | 1.65 (defaults file) |
| `r_cutsceneFx` | 31 (= no restriction, check semantics) | as today |
| `r_deluxeSpecular`, `r_cubeMapping`, sun/shadow/lightmap set | upstream values | pinned in `codmod.cfg` (moved out of `run.sh`) |
| Tuning (`r_bloomIntensity`, `r_grade*`, `r_ssao*`, `r_cubemap*`, `r_codSpecDirectional`) | unchanged, inert while the feature is off | pinned where needed |

### 3c. Client, UI, sound
| Behaviour | New switch (engine default = vanilla) | codmod |
|---|---|---|
| Intro always plays, ignores `com_introPlayed` | `cl_introAlways 0` (vanilla: once) | 1, plus `cod_skipIntro` menu option |
| Any key skips cinematics | `cl_cinematicAnyKeySkip 0` | 1 |
| Cutscene letterbox change | `cl_cinLetterbox` (vanilla look by default) | codmod value |
| Cursor hotspot at the art's top-left tip, square on widescreen | `ui_cursorTipHotspot 0` | 1 (needs the codmod cursor art anyway) |
| 4:3 briefing + blurred backdrop | `ui_briefing43 0` | 1 |
| HRTF | `s_alHRTF 0` | 1 (defaults file) |
| Gamepad on | upstream `in_joystick 0` | 1 (defaults file; latched, now applied by the hook) |
| `cod_pad*` aim assist, snap, gyro | Only active with a pad; keep, but values move to the mod | set in mod cfgs |

Names above are proposals; the implementer checks for existing cvars first.

### 3d. Build
Release builds already use `-O3 -ffast-math` (`iortcw/SP/Makefile`, x86_64 Linux). `-march=native` would make
binaries non-portable and LTO is untested; neither is part of this plan.

## 4. Stays in the engine, on by default (fixes, not opinions)
Perf/bug fixes that do not change the look or feel: no per-frame `glFinish` (`r_swapFinish 0`), async flares,
SMAA stencil, GTAO depth mips, cubemap batching fix and merge, specular hotspot fix, frame pacer/limiter/vsync modes,
view clock (`cl_viewSmooth 1`), soft `vid_restart`, Wayland fullscreen, HD `ResampleTexture` overflow, savegame
`cameraPortal` crash, reload/fire-anim races, UI editfield/popup/save-list fixes, `MAX_CONSOLE_LINES 64`, AO/fog and
cutscene viewport fixes. Capabilities with no effect unless used (MJPEG cinematics, extra video modes, language
tables, pad support, profiler) also stay.

## 5. Decisions for the user
- **D1 mechanism:** generic `<fs_game>_defaults.cfg` + `<fs_game>.cfg` engine hooks (recommended) vs keeping
  `run.sh +set/+exec` (mod only works through our script).
- **D2 switches:** master `cod_enable 0` with per-feature flags under it (recommended: one line turns codmod on,
  a mod can still drop single features) vs every feature flag defaulting to 0.
- **D3 tuning values:** move all `cod_*` values into `codmod.cfg` and set code defaults to vanilla equivalents
  (recommended) vs only flip the switches and keep CoD numbers in C.
- **D4 naming:** keep `cod_*` / `r_cod*` names for now (recommended: renaming breaks saved configs, menus and docs;
  can be a later pass) vs rename to neutral names now.
- **D5:** the section 4 list stays on by default in the engine. Flag anything you consider an opinion.

## 6. Steps and who does them

Edits in `iortcw/` are committed in the submodule and pushed to the fork, then the outer repo bumps the pointer.
Subagents edit and compile-check only; I run the single `scripts/build.sh --install` per wave and the tests, to avoid
parallel builds in one tree.

| # | Step | Agent | Files |
|---|---|---|---|
| 0 | Baseline: `scripts/shots.sh` set + bench run of today's codmod (reference for "identical") | me | - |
| 1 | Engine config hooks (section 2) | Sonnet | `qcommon/common.c` |
| 2 | Game modules: master default 0, gate audit, vanilla-equivalent tuning defaults, script that dumps the table to cfg | Sonnet | `game/*`, `cgame/*`, `scripts/` |
| 3 | Renderer defaults (3b) | Sonnet | `rend2/tr_init.c` (+ gating checks in `tr_shader.c`, `tr_light.c`) |
| 4 | Client/UI/sound switches (3c) | Sonnet | `qcommon/common.c` intro block, `client/cl_cin.c`, `client/cl_keys.c`, `ui/ui_main.c`, `ui/ui_shared.c`, `client/snd_openal.c` |
| 5 | Mod side: `codmod_defaults.cfg`, extend `codmod.cfg`, trim `run.sh` (keep fs_game, paths, backups, bench overrides), menu Reset actions -> deltas | Sonnet | `mod/codmod/*`, `scripts/run.sh`, `menu-deltas/` |
| 5b | Menu layers (2b): sort deltas into `engine/` and `codmod/`, two-pass `build-menus.sh`, engine rows for `main` | Sonnet | `menu-deltas/`, `scripts/build-menus.sh`, `scripts/menus.py`, `scripts/install.sh` |
| 6 | Docs: AGENTS.md settings rule, `docs/menus.md`, `docs/architecture.md` section 0, README, memory bank, decisions.md + jevmem | Haiku (docs text), me (decisions) | docs |
| 7 | Verify (section 7) and report to the user for in-game check | me + user | - |

Steps 2, 3 and 4 touch different files and run in parallel; step 1 runs alongside them (step 4 also edits
`common.c`, so 1 and 4 go to the same agent or run one after the other). Step 5 needs 1-4 merged. Step 6 last.

## 7. Verification
1. **codmod identical:** shots set and bench vs step 0 baseline (`shots-diff.py`), with the user's real home.
2. **codmod fresh install:** throwaway `RTCW_HOMEPATH`, launch without `run.sh` latches; check first-launch
   defaults (resolution, AA, bloom, binds, pad) come from `codmod_defaults.cfg`; change a menu option, relaunch,
   confirm it persists; Reset restores the mod defaults.
3. **Vanilla:** `scripts/run.sh --vanilla` (install with `--vanilla`): original movement speeds, lean, HUD, health,
   ammo, crosshair, no bloom/grade/AO/specular, intro once, original menus.
4. Savegame from before the change still loads in codmod.
5. User in-game check of both modes before committing. Safety rules apply (rend2 present/2D path untouched,
   `wolfconfig.cfg` never edited).

## 8. Risks
- A codmod path that is not gated shows up in vanilla: the step 2 audit plus the vanilla test catch it.
- Latched cvars set from the defaults file after renderer init: the hook runs before `CL_Init`, check the order.
- A menu row whose cvar loses its code default: first launch shows the vanilla value until the defaults file runs;
  covered by fresh-install test.
- `run.sh` bench overrides (`RTCW_STARTUP_SETS`) still need `+set`; keep that path.

## 9. Phase 2 (separate, after this split is verified by the user): remove opengl1 entirely

**Status: implemented 2026-10-18 (SP only; MP untouched), pending user check.** `code/renderer/` is deleted, shared
headers live in `code/renderercommon/`, the Makefile builds only rend2, `cl_renderer` is gone (`CL_InitRef`
always loads `renderer_sp_rend2`), and the graphics presets no longer set it.

Rip the opengl1 renderer out of the fork and the project completely: delete `code/renderer/` opengl1 sources, its
Makefile targets and the `CL_InitRef` fallback, `install.sh` entry, menu/doc mentions. Shared headers the client and
rend2 include (`tr_public.h`, `tr_types.h`, `iqm.h`) move where rend2/client can use them, so nothing of the old
renderer is left. No tag or kept copy. Only starts once phase 1 (sections 1-8) is checked and approved.
