# Menus: building and editing rules

Menus come in **two layers**. The engine layer is for engine features any player can use; the codmod layer is the
CoD-style look and the mod's own rows, built on top of the engine layer.

| Layer | Source dir (generated, git-ignored) | Deltas in git | Pack | Installed to |
|---|---|---|---|---|
| Engine (in the fork) | `iortcw/SP/menus/ui/` | `iortcw/SP/menus/deltas/` (on RTCW's original menus) | `iortcw/SP/menus/sp_zz_engine_menus.pk3` | `run/main/` (always; codmod loads `main/` too) |
| Codmod | `mod/codmod/ui/` | `mod/codmod/menu-deltas/codmod/` (on the engine-layer result) | `mod/codmod/codmod_menus.pk3`, `codmod_hud.pk3` | `run/codmod/` |

The game loads the packed pk3s, never the loose files. In vanilla (`fs_game main`) only the engine layer applies, on
RTCW's original menu layout; codmod's menus replace it. A `.menu` file that exists in the engine layer but has no
codmod delta (the video-mode and language popups) is copied unchanged into the codmod layer.

The engine layer and the delta builder (`iortcw/SP/menus/menudelta.py`) live in the engine fork, so the fork builds
its own menus without knowing codmod exists: `iortcw/SP/run-sp.sh` builds them and runs the fork as plain RTCW.
`scripts/menus.py` imports `menudelta.py` and adds only the codmod layer on top. Engine-layer deltas are committed in
the submodule (and pushed to the fork), codmod deltas in this repo.

## Which layer does a row belong in

- **Engine layer**: rows for cvars that the engine/fork implements and that work without the mod: `r_ao`, `r_aa`,
  `r_bloom`, `r_grade`, `r_codSpecular`, `r_flashlightShadow`, `r_cameraExposure`, gamma, `r_displayMode`, `r_vsync`,
  `com_maxfps`/`com_maxfpsMenu`, video-mode popup, shadow size/filter, anisotropic filter, `s_alHRTF`, `in_joystick`,
  `cod_padSensX/Y`, `cod_padGyro`, `cod_padGyroSens` (read by `cl_input.c`, so engine despite the prefix),
  `cod_subtitles`/`cod_subtitleScale`, text/audio language popups. Rules: no references to codmod cfgs, codmod art
  or `cod_*` gameplay cvars (those live in `bg_cod.c`); no reset/recommended button that execs a codmod file; list
  labels carry no "(default)" tag (the vanilla defaults are "feature off"). They are added to RTCW's own menus in
  `system.menu`/`ingame_system.menu` (new Display and Effects tabs, HRTF on the Sound tab), `options.menu`/
  `ingame_options.menu` (View tab: subtitles, language), `controls.menu`/`ingame_controls.menu` (Pad tab), and
  `menus.txt` (loads the three popups; they are only listed there, see Rules).
- **Codmod layer**: the CoD-style main/pause/settings layout (vertical lists, hub, tabs), cursor art, `cod_*` gameplay
  rows (flashlight, auto-aim, skip intro, debug HUD), the bench row, "restore recommended" buttons that exec codmod
  cfgs, `mods.menu` restyle. Codmod's `options.menu`, `game.menu`, `controls_pad.menu` ... still show the same engine
  features in the CoD layout; a new engine feature therefore needs a row in both layers.

Engine-layer edits do not flow into the codmod copies automatically: the codmod delta stores the finished codmod file
as a diff against the engine file, so adding an engine row never changes codmod's menus unless you also edit them.

## How menus are stored (licensing)

Our `.menu` files are edited versions of RTCW's own menus, which are game data (not GPL) and must not be
redistributed. Git therefore tracks **deltas only**: `mod/codmod/menu-deltas/<layer>/<name>.menu.delta` holds our added or
written lines plus the line ranges of the base to replace. Anything we reused from an original (including blocks
moved between menus) is stored as a *reference* (`=ui/options.menu 120 168`, meaning "lines 120 to 167 of that file in
your paks"), not as text; only braces, blank lines and a few one-line property assignments stay literal.
An engine delta's base is the original in your paks; a codmod delta's base is the engine-layer file (header
`... layer=engine`), or an original for codmod-only menus.
`scripts/menus.py` reads the originals from your RTCW paks, checks their SHA-256, applies the deltas (engine first),
and writes the full files to the two ui dirs (git-ignored, each has a `.gitignore`). The pk3s are generated and
git-ignored too. `menudef.h` (GPL source), codmod's `menus.txt`/`ingame.txt`/`hud.txt` and `glyphs/` are our own
or GPL and stay in git (the engine layer's `menus.txt` is a delta on RTCW's).

## Build and install

1. First time / after `git pull`: `scripts/setup.sh` or `scripts/install.sh` run `scripts/build-menus.sh`, which
   generates missing or outdated ui files from the deltas and packs all pk3s (python3 only; no `zip` needed).
2. Edit the ui files of the layer your change belongs to: `iortcw/SP/menus/ui/*.menu` (engine rows, vanilla layout)
   or `mod/codmod/ui/*.menu` (codmod layout and rows). Add a menu file to `menus.txt` / `ingame.txt` (codmod) or to
   the engine layer's `txt` list in `menudelta.py` (engine: only `menus.txt` is supported today).
3. `scripts/build-menus.sh` repacks the pk3s; `scripts/install.sh` also copies them to `run/main/`
   (`sp_zz_engine_menus.pk3`) and `run/codmod/`.
4. **Before committing**: `scripts/build-menus.sh --export` (or `scripts/menus.py export`) refreshes the deltas of
   **both** layers from their edited files: engine dir -> `iortcw/SP/menus/deltas/`, codmod dir -> `mod/codmod/menu-deltas/codmod/`
   (the layer is simply the directory you edited). A codmod file identical to the
   engine file has no delta. Commit the `.delta` files, never the generated `.menu` files. A locally edited file is
   never overwritten by the build; it prints a note if its delta is stale. If you change an engine file and its
   codmod counterpart is derived from it, export rebases the codmod delta onto the new engine file.
5. Restart the game: menus are parsed once at startup (never kill it, quit cleanly).

A new menu file with little in common with the originals is still stored as a delta against the closest original, so
the same flow applies. If the game shows old menus, the pk3 in `run/main/` or `run/codmod/` is stale (`cmp` it against
`iortcw/SP/menus/` / `mod/codmod/`). If your RTCW paks differ from the 1.41 data the deltas were made against, the
build stops with a clear error.

**Pak name gotcha:** the engine sorts `sp_*` paks after all others and renames `zz_*` to `sp_` when opening. A pk3 in
`run/main/` therefore has to start with `sp_` (and not be `sp_pak<N>`) to override RTCW's menus, hence
`sp_zz_engine_menus.pk3`. In `run/codmod/` the game directory order already wins, so plain `codmod_*.pk3` names work;
never name them `zz_*`.

## Rules

- Never name a pk3 `zz_*`: the engine renames those to `sp_` (see `codmod.cfg`, `memory/decisions.md`).
- Options live in `options.menu` (main) and `ingame_options.menu` (pause). Change both and keep their rows identical
  (the benchmark rows exist only in the main one). `system.menu` / `ingame_system.menu` are redirect stubs.
- Options page: tabs `ctr_display` (items `name display`: video mode, display mode, vsync, FPS limits, frame pacing), `ctr_graphics` (`name graphics`) and `ctr_advanced` (`name advanced`). Display Mode (windowed / borderless / fullscreen) is the cvar `r_displayMode`, a view over `r_fullscreen` + `r_noborder` (`CL_ApplyDisplayMode` in cl_main.c); borderless forces `r_mode -2`. Every row has
  `group grpOptions`, `rect 240 <y> 320 11`, 11 px pitch. Tabs show their items with
  `hide grpOptions ; show <name> ; show graphicsapply`. A tab's last row must stay above the Apply button (y 418).
- Text does not wrap or clip: at scale .17 about 55 characters fit from x=240. Split long notes into several lines.
- `cvarStrList` entries need commas (`"Label", "value", ...`); `cvarFloatList` does not. Without them the value shows blank.
- The video-mode list is rebuilt in C (`UI_RefreshVidModeList`, ui_shared.c); the `.menu` list is only a seed.
  Clicking Video Mode opens `vidmode_popmenu` (scrollable `FEEDER_VIDMODES` list); it no longer click-cycles.
  Shared popups used from both main and pause (`vidmode.menu`, language popups, …) must be listed only in
  `menus.txt` — both menu lists are loaded together, and a duplicate `loadMenu` creates two menus with the same
  name so open/close hit different copies.
- Do not use `uiScript glCustom`; the quality-preset cvar `ui_glCustom` is gone.

## Settings must persist

The engine runs a mod's two config hooks around the user's config on every launch (and again on menu Reset, via
the `execmodcfg` command): `default.cfg` → `<fs_game>_defaults.cfg` → `wolfconfig.cfg` → `autoexec.cfg` →
`<fs_game>.cfg`, all before the renderer and input start, then command-line `+set` on top. So:

- **User-facing settings** (anything in an options menu): the engine/game code keeps the vanilla default
  (`CVAR_ARCHIVE`); codmod's recommended value is a `seta` in `mod/codmod/codmod_defaults.cfg` (which also execs
  `codmod_binds.cfg` and `codmod_gfxdefaults.cfg`). It runs before `wolfconfig.cfg`, so the user's saved choice
  wins and the codmod value only shows on first launch and after Reset. Latched cvars (shadow size, SSAO, AF,
  r_mode) need nothing extra: the configs run before the renderer starts.
- **Internal / pinned config** (tuning, forced engine cvars): `set` in `mod/codmod/codmod.cfg` (runs last, every
  launch); gameplay tuning lives in `codmod_tuning.cfg`, which `codmod.cfg` execs first.

Never put a menu cvar in `codmod.cfg` or a `+set` in `scripts/run.sh`: both run every launch and silently undo the
user's choice. Never edit the user's `wolfconfig.cfg` (`docs/testing.md`, Safety rules).

## What is exposed, and why

GRAPHICS shows only settings with a real effect (mode, fullscreen, vsync, FPS cap, anti-aliasing,
gamma, HDR exposure).
ADVANCED lists the rest with each default tagged "(default)". Settings tied to the sun/shadow pipeline (depth
prepass, force sun, HDR chain) stay hidden because toggling them alone is misleading; see `docs/performance.md`.
First-launch display defaults: SMAA High, vsync Triple Buffer, no FPS cap, desktop resolution (`r_mode -2`), fullscreen.
