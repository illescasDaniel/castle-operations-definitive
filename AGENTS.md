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
repo in `iortcw/` (clone of the fork https://github.com/illescasDaniel/iortcw, branch `main`; git-ignored by the outer
repo, `upstream` remote = ioRTCW). Engine/game-code commits go there, not in the outer repo (there is no `patches/`
any more). Check `git status` in both repos.

## Building

Build with `scripts/build.sh --game-only --install` (drop `--game-only` when engine files changed). `build.sh` alone
leaves stale modules in `run/`, so the game ignores your change; `--install` runs `scripts/install.sh` afterwards.

## Menus

Edit `mod/codmod/ui/*.menu` (git-ignored, generated from RTCW's paks + deltas), then `scripts/build-menus.sh --export` and commit the `menu-deltas/*.delta` files; never commit generated `.menu` files or the menu/hud pk3s (RTCW menus are not redistributable). Rules in `docs/menus.md`.

## User settings vs internal config

A user-facing setting (anything in an options menu) has a default for first launch and for the Reset action, and the
user's change must persist across launches. Put its default in the code (`bg_cod.c`, with `CVAR_ARCHIVE`) and its
reset value in `mod/codmod/codmod_binds.cfg`; never `set`/`seta` it in `codmod.cfg` or `run.sh` `+set`, which run
every launch and silently undo the choice. Internal/pinned config (tuning, forced engine cvars) belongs in
`codmod.cfg`. Details and latched-cvar handling in `docs/menus.md` ("Settings must persist").

## Running the game

Never kill the game forcefully (`kill`, `pkill`, `killall`) unless it is stuck or not responding. A forced exit makes
the system show a "launch with safe options" popup on the next start, which blocks automatic launches and that I
may not be able to dismiss. Quit cleanly (`quit` command / in-game menu) and only kill a genuinely hung process.
