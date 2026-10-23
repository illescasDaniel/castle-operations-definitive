# rtcw-mcp

Local MCP server (stdio, Python) that lets an agent drive the game headless: screenshots at a position, texture/shader
normal-map coverage, console output, load-time profiling, benchmarks, image diffs and builds. It wraps the existing
scripts in `scripts/` where one fits (`load-test.sh`, `bench.sh`, `spin-test.sh`, `build.sh`) and re-implements the
`shot-at.sh` flow for the screenshot / console / coverage tools (they need per-spot log capture, which `shot-at.sh`
discards). Nothing is registered globally: you decide.

## Setup

```bash
cd tools/rtcw-mcp
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt   # mcp<2, pillow, numpy
.venv/bin/python -m unittest discover tests     # unit tests, mocked launcher, no game started
.venv/bin/python tests/smoke_stdio.py           # starts server.py over stdio, lists tools, calls the read-only ones
```

Register it for this project only (writes `.mcp.json`; or use `--scope user` for everywhere):

```bash
claude mcp add rtcw --scope project -- /home/daniel/Projects/Code/Games/rtcw-cod/tools/rtcw-mcp/.venv/bin/python /home/daniel/Projects/Code/Games/rtcw-cod/tools/rtcw-mcp/server.py
```

Game runs take minutes. Claude Code's MCP tool timeout is long by default, but if you lowered it, set
`MCP_TOOL_TIMEOUT=900000` (ms). The server sends progress pings while the game runs.

## Tools

| Tool | What it does |
|---|---|
| `screenshot(map, spots[], skip_intro=auto, settle, wait_frames, cvars, label, hud, commands, max_width, return_images)` | Loads `map` (`spdevmap`, headless gamescope 1920x1200), god + notarget + no gun + no 2D, teleports to each spot, saves `benchmarks/shots/<label>/spotNN.tga` (+ `.png`, `.small.png`) and returns the paths and the downscaled images. |
| `texture_coverage(map, spots[], shader_filter, ...)` | Runs the `normalcov` console command at each spot and returns the parsed table: per shader `count`, diffuse `image`, `status` (`parallax`, `_nh found, parallax off`, `normal map`, `NO NORMAL MAP`, `not lightall`, `normals off (cvars)`), per-status totals, covered %. |
| `console_log(map, commands[], spot, grep, max_lines, ...)` | Runs console commands at a spot and returns the output they produced (e.g. `viewpos`, `gpuprof`). `quit`/`bind`/`exec`/`vid_restart` are refused. |
| `load_times(maps[], level_change, profile_level)` | Wraps `scripts/load-test.sh`: total ms, presents, max gap@stage, p95, gaps > 33 ms (+ gap list). |
| `benchmark(kind=normal\|spin, cvars, runs, label, max_ratio, gpuprof)` | `bench.sh` (avg / 1% low / P99 / hitches per run + median, appended to `benchmarks/results.csv`; `gpuprof=true` adds the per-pass GPU ms table via `bench.sh --gpuprof`) or `spin-test.sh` (GPU ms still vs turning, PASS/FAIL). Always headless. |
| `compare_shots(a, b)` | Two images or two labels: differing-pixel %, max/mean diff, and an "A \| B \| diff x16" PNG. No game. (`scripts/shots-diff.py` handles both `shot*.tga` and `spot*.tga` sets.) |
| `build(game_only=true, install=true)` | `scripts/build.sh [--game-only] --install`; returns warning/error counts and the first diagnostics (output tail only on failure). Use `game_only=false` when engine/renderer files changed. |
| `game_status`, `list_maps`, `known_spots(map)` | Is a game/build/bake running; maps in `run/main/*.pk3`; spots from `benchmarks/spots-*.txt` plus documented ones. Resources: `rtcw://spots`, `rtcw://gotchas` (this file). |

Example (the trainyard stone wall; `town_wall/town_c22a1burn` is expected as `parallax` with the bright-target pack):
`texture_coverage(map="trainyard", spots=["-1012.1 481.6 88.1 -143.3 9.5"], shader_filter="town_wall")`.
A spot is `x y z yaw pitch`; the console command `viewpos` prints a ready `setviewpos x y z yaw pitch` line (decimal
commas are accepted).

## Safety behaviour

- **One game at a time.** A lock file (`$XDG_RUNTIME_DIR/rtcw-mcp.lock`) plus a `pgrep iowolfsp` check: every tool that
  launches the game (and `build`) refuses with a message if one is already running, since that may be you playing.
  Builds are refused while the game runs and the other way round.
- **A running `height_bake.py` is reported as a warning** (half-written pack), not a refusal.
- **`wolfconfig.cfg` is backed up and restored** around every run (as `shot-at.sh` does; `run.sh` also keeps its rolling
  backups). Nothing here touches the rend2 present/2D path, the submodule, cfgs or docs.
- **Clean exits only.** Scripts end with `quit` after generous waits. The only kill is a genuinely hung run after the
  timeout (600 s per map session, longer for the script wrappers): SIGTERM to the process group, SIGKILL as a last
  resort, and the result carries a `HUNG` warning (the next launch may show the "safe options" popup).
- Scripted runs are always headless gamescope; there is no on-screen option.
- `cvars` are forced with startup `+set` (latched cvars work; max 8, values `[\w.+-/]` only). Archived cvars set this
  way are saved on quit, which the wolfconfig restore undoes.

## Gotchas built in (from the project notes)

- **Intro cutscenes:** `escape1` starts with a cutscene and `crypt1` screenshots are black unless it is skipped. The
  tools send `cmd cameraInterrupt` automatically on those maps (`skip_intro=null`); override with true/false. Add maps to
  `INTRO_SKIP_MAPS` in `rtcw_core.py` when you find more.
- **Never `+quit` during a map load** (segfault): the console script waits `settle` frames (default 400; frames, not ms)
  before dismissing the "continue" prompt (`uiclick 612 466`), and quits only after the last step.
- Console output comes from `run/home/codmod/rtcwconsole.log` (`run.sh` sets `logfile 2`); the log is truncated at the
  start of each run and the tools cut it into per-spot sections with `MCPMARK` echo lines.
- A fresh empty `fs_homepath` crashes at start: the tools always use the real `run/home`.
- A stale `run/codmod/codmod_height_legacy.pk3` sorts after `codmod_height.pk3` and silently overrides it (walls look
  shredded): check before judging relief.
- Rebuild with `build` (or `scripts/build.sh --game-only --install`; drop `--game-only` after engine changes): without
  `--install` `run/` keeps stale modules.
- `normalcov` reports on the *next rendered frame*; the tool waits 3 frames after it. Needs the rend2 build from 2026-10-23+.

## Files

`server.py` (MCP tools), `rtcw_core.py` (cfg builder, log parsers, locked runner; no MCP imports), `tests/`
(`test_core.py` mocked, `smoke_stdio.py` protocol check), `requirements.txt`, `.gitignore` (`.venv/`).
