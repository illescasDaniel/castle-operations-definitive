# Menus: building and editing rules

Menu sources live in `mod/codmod/ui/*.menu`. The game loads the packed `mod/codmod/codmod_menus.pk3`, never the loose files.

## How menus are stored (licensing)

Our `.menu` files are edited versions of RTCW's own menus, which are game data (not GPL) and must not be
redistributed. Git therefore tracks **deltas only**: `mod/codmod/menu-deltas/<name>.menu.delta` holds our added or
written lines plus the line ranges of the original to replace. Anything we reused from an original (including blocks
moved between menus) is stored as a *reference* (`=ui/options.menu 120 168`, meaning "lines 120 to 167 of that file in
your paks"), not as text; only braces, blank lines and a few one-line property assignments stay literal.
`scripts/menus.py` reads the originals from your RTCW paks, checks their SHA-256, applies the delta, and writes the full file to `mod/codmod/ui/`
(git-ignored, see `ui/.gitignore`). The pk3s `codmod_menus.pk3` and `codmod_hud.pk3` are generated and git-ignored too.
`menudef.h` (GPL source), the `*.txt` file lists and `glyphs/` are our own or GPL and stay in git.

## Build and install

1. First time / after `git pull`: `scripts/setup.sh` or `scripts/install.sh` run `scripts/build-menus.sh`, which
   generates missing or outdated `ui/*.menu` from the deltas and packs both pk3s (python3 only; no `zip` needed).
2. Edit `mod/codmod/ui/*.menu` (and `menus.txt` / `ingame.txt` if you add a menu file).
3. `scripts/build-menus.sh` repacks the pk3s; `scripts/install.sh` also copies them to `run/codmod/`.
4. **Before committing**: `scripts/build-menus.sh --export` (or `scripts/menus.py export`) refreshes the deltas from your
   edited files. Commit the `.delta` files, never the generated `.menu` files. A locally edited file is never
   overwritten by the build; it prints a note if its delta is stale.
5. Restart the game: menus are parsed once at startup (never kill it, quit cleanly).

A new menu file with little in common with the originals is still stored as a delta against the closest original, so
the same flow applies. If the game shows old menus, `run/codmod/codmod_menus.pk3` is stale (`cmp` it against `mod/codmod/`).
If your RTCW paks differ from the 1.41 data the deltas were made against, the build stops with a clear error.

## Rules

- Never name the pk3 `zz_*`: the engine renames those to `sp_` (see `codmod.cfg`, `memory/decisions.md`).
- Options live in `options.menu` (main) and `ingame_options.menu` (pause). Change both and keep their rows identical
  (the benchmark rows exist only in the main one). `system.menu` / `ingame_system.menu` are redirect stubs.
- GRAPHICS page: tabs `ctr_graphics` (items `name graphics`) and `ctr_advanced` (`name advanced`). Every row has
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

Rule of thumb: **user-facing settings** (anything in an options menu, e.g. gamepad sensitivity, auto-aim, gyro) get a
default in code (`bg_cod.c` with `CVAR_ARCHIVE`, or the engine `Cvar_Get`) plus a reset value in `codmod_binds.cfg`;
they are never set in `codmod.cfg`. **Internal config** (tuning, pinned engine cvars) stays in `codmod.cfg`.

A cvar offered in a menu must not be forced on every launch. `codmod.cfg` and the `+set` lines in `scripts/run.sh`
are applied each start and would silently undo the user's choice. Put the recommended value in
`mod/codmod/codmod_gfxdefaults.cfg` (graphics) or the display block of `codmod_binds.cfg`, both applied on first
launch / reset only. Latched cvars (shadow size, SSAO, AF, r_mode) also need a `+set` in `run.sh`, guarded so it
runs only when `wolfconfig.cfg` has no saved value. The command line drops `+` commands past a limit, so do not
add more. Never edit the user's `wolfconfig.cfg` (`docs/testing.md`, Safety rules).

## What is exposed, and why

GRAPHICS shows only settings with a real effect (mode, fullscreen, vsync, FPS cap, anti-aliasing, brightness).
ADVANCED lists the rest with each default tagged "(default)". Settings tied to the sun/shadow pipeline (depth
prepass, force sun, HDR chain) stay hidden because toggling them alone is misleading; see `docs/performance.md`.
First-launch display defaults: SMAA High, vsync Triple Buffer, no FPS cap, desktop resolution (`r_mode -2`), fullscreen.
