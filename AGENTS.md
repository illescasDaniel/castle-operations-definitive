# Castle Operations Definitive (`codmod`) — RTCW remaster

Single-player **Return to Castle Wolfenstein** remaster via ioRTCW: CoD4-style
movement/gunplay, plus optional local AI HD textures and HD audio (tools in
`tools/`; generated pk3s stay private). Start with `docs/plan.md` (read order
at the top of that file).

## Memory bank

Project state lives in `memory/` (git-tracked, so it follows the branch). At session start, read
`memory/activeContext.md` then `memory/progress.md`. Update on these triggers only: a task is completed or discovered
(`progress.md`); focus changes, a blocker is hit or work concludes (`activeContext.md`); a significant technical
decision is made (`decisions.md`, append-only, newest first). Full protocol: the `memory-bank` skill.

## Long-term memory (jevmem)

The `jevmem` MCP server stores dated facts that stay true: decisions with reasons, bug causes, gotchas, preferences.
Write them with `memory_write` right after they happen; recall with `memory_recall`. Never store current state or next
steps there (that goes in `memory/`). A significant decision gets both a `decisions.md` entry and a one-fact jevmem
note. Full protocol: the `jev-memory` skill.

## Safety rules

Never alter the rend2 present/2D path or the user's `wolfconfig.cfg` without user verification; both broke the
game once (no HUD, wiped binds). Rules and cause in `docs/testing.md` ("Safety rules"). The engine is a separate
repo in `iortcw/`, a git submodule of the outer repo (fork https://github.com/illescasDaniel/iortcw, branch `main`; `iortcw/SP/run-sp.sh` runs it standalone as plain RTCW;
`upstream` remote = ioRTCW). Engine/game-code commits go in the submodule repo and are pushed to the fork; then the
outer repo commits the bumped submodule pointer (there is no `patches/` any more). Check `git status` in both repos.

## Building

Build with `scripts/build.sh --game-only --install` (drop `--game-only` when engine files changed). `build.sh` alone
leaves stale modules in `run/`, so the game ignores your change; `--install` runs `scripts/install.sh` afterwards.

## Menus

Two layers. Engine-feature rows (usable by plain RTCW) go in `iortcw/SP/menus/ui/*.menu` (engine layer and its builder `menudelta.py` live in the fork), the CoD layout and `cod_*` gameplay rows in `mod/codmod/ui/*.menu`; both are git-ignored, generated from RTCW's paks + deltas. Then `scripts/build-menus.sh --export` and commit the `.delta` files (`iortcw/SP/menus/deltas/` in the submodule, `mod/codmod/menu-deltas/codmod/` here); never commit generated `.menu` files or the menu/hud pk3s (RTCW menus are not redistributable). Rules in `docs/menus.md`.

## User settings vs internal config

Three kinds of value, each in one place:

- **User-facing setting** (anything in an options menu, `CVAR_ARCHIVE`): the engine's code default is the **vanilla**
  value, so a plain RTCW install behaves like RTCW. The mod's first-launch and Reset value is a `seta` in
  `mod/codmod/codmod_defaults.cfg`. That file runs before `wolfconfig.cfg`, so the user's saved choice wins and
  persists across launches. Binds are execed from it (`codmod_binds.cfg`).
- **Internal or pinned config** (forced engine cvars, feature switches): `set` in `mod/codmod/codmod.cfg`, which runs
  after `wolfconfig.cfg` on every launch. Never a cvar that an options menu changes.
- **`cod_*` tuning values**: `mod/codmod/codmod_tuning.cfg`, execed by `codmod.cfg`.

Never `set`/`seta` a user-facing setting in `codmod.cfg`, `codmod_tuning.cfg` or `run.sh` `+set`: those run every
launch and silently undo the choice. `run.sh` passes only paths and `fs_game`. Hook order and latched-cvar handling are
in `docs/architecture.md` (section 0); menu rules and the "Settings must persist" details in `docs/menus.md`.

## Running the game

Never kill the game forcefully (`kill`, `pkill`, `killall`) unless it is stuck or not responding. A forced exit makes
the system show a "launch with safe options" popup on the next start, which blocks automatic launches and that I
may not be able to dismiss. Quit cleanly (`quit` command / in-game menu) and only kill a genuinely hung process.

## Benchmarks run off-screen

Always run benchmarks and scripted measurement runs off-screen, never as a visible window: `scripts/bench.sh` (headless
gamescope by default; `BENCH_ONSCREEN=1` opts out), `SHOT_HEADLESS=1 scripts/shots.sh ...` / `shot-at.sh`, and
`scripts/spin-test.sh`; for ad-hoc scripted runs use
`gamescope --backend headless -W 1920 -H 1200 -- scripts/run.sh --windowed 1920x1200 ...`. Back up and restore
`wolfconfig.cfg` around them (`set` of archived cvars is saved on quit).

## Driving the game from an agent

Game runs go through the `rtcw` MCP server (`mcp__rtcw__*`, `tools/rtcw-mcp/README.md`): `screenshot`, `texture_coverage`, `console_log`, `load_times`, `compare_shots`, `build`, `benchmark`, `known_spots`, `game_status`. It runs the game headless, one instance at a time, and refuses while the user is playing; don't start the game any other way. Details, spots and gotchas: `tools/rtcw-mcp/README.md`. Prefer it to `scripts/shot-at.sh` and `bench.sh`, which it wraps. If it refuses (the user is playing), wait; don't work around it.
