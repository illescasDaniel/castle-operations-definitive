#!/usr/bin/env python3
"""rtcw-mcp: drive the RTCW/codmod game headless from an agent (stdio MCP server). See README.md."""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP, Image
from pydantic import Field

import rtcw_core as core
from rtcw_core import RtcwError, Step

mcp = FastMCP("rtcw", instructions=(
    "Drives the Return to Castle Wolfenstein / codmod remaster headless (gamescope, off-screen). One game instance at "
    "a time; refuses if the user is playing. Tools: screenshot, texture_coverage, console_log, load_times, benchmark, "
    "compare_shots, build, game_status, list_maps, known_spots. A map load takes ~10-60 s; calls can take minutes."))

Spot = Annotated[str | list[float], Field(description="'x y z yaw pitch' (the console command `viewpos` prints a "
                                          "ready `setviewpos x y z yaw pitch` line; decimal commas accepted)")]


def _fail(e: Exception) -> dict:
    return {"ok": False, "error": str(e)}


async def _in_thread(ctx: Context | None, fn, *a, **kw):
    """Run blocking work off the event loop, sending a progress ping every ~10 s so clients do not time out."""
    loop = asyncio.get_running_loop()
    n = {"i": 0}

    def tick():
        if ctx is not None:
            n["i"] += 1
            asyncio.run_coroutine_threadsafe(ctx.report_progress(n["i"], None, "game running"), loop)

    return await asyncio.to_thread(fn, *a, tick=tick, **kw)


def _tail(text: str, n: int = 40) -> str:
    return "\n".join(text.strip().splitlines()[-n:])


# ------------------------------------------------------------------ screenshot

def _do_screenshot(map: str, spots: list, skip_intro, settle, cvars, label, hud, wait_frames, max_width,
                   commands, tick=None):
    core.check_map(map)
    parsed = [core.parse_spot(s) for s in spots]
    if not parsed:
        raise RtcwError("give at least one spot")
    label = label or f"mcp-{map}-{time.strftime('%Y%m%d-%H%M%S')}"
    if not re.match(r"^[\w.\-]+$", label):
        raise RtcwError("label: letters, digits, . _ - only")
    cmds = [core.check_console_cmd(c) for c in commands or []]
    steps = [Step(spot=s, commands=cmds, screenshot=f"codmod_mcp_{i:02d}", settle=wait_frames)
             for i, s in enumerate(parsed, 1)]
    r = core.run_steps(map, steps, cvars=cvars, skip_intro=skip_intro, settle=settle, hud=hud, tick=tick)
    out_dir = core.SHOTS_DIR / label
    out_dir.mkdir(parents=True, exist_ok=True)
    shots, missing = [], []
    for i, s in enumerate(parsed, 1):
        src = core.HOME_CFG / "screenshots" / f"codmod_mcp_{i:02d}.tga"
        if not src.is_file():
            missing.append(i)
            continue
        dst = out_dir / f"spot{i:02d}.tga"
        shutil.move(str(src), dst)
        png = core.downscale_png(dst, out_dir / f"spot{i:02d}.png", 100000)
        small = core.downscale_png(dst, out_dir / f"spot{i:02d}.small.png", max_width)
        shots.append({"spot_index": i, "spot": s, "tga": str(dst), "png": str(png), "small_png": str(small)})
    res = {"ok": bool(shots) and not missing, "map": map, "label": label, "dir": str(out_dir), "shots": shots,
           "skip_intro": r["skip_intro"], "seconds": r["seconds"], "completed": r["completed"],
           "warnings": r["warnings"], "errors": r["errors"]}
    if missing:
        res["missing_spots"] = missing
    return res


@mcp.tool()
async def screenshot(map: str, spots: list[Spot], skip_intro: bool | None = None, settle: int = core.DEFAULT_SETTLE,
                     wait_frames: int = 20, cvars: dict[str, str] | None = None, label: str | None = None,
                     hud: bool = False, commands: list[str] | None = None, max_width: int = 1280,
                     return_images: bool = True, ctx: Context | None = None) -> list:
    """Load `map` headless (god, notarget, no gun, no HUD), teleport to each spot and save a screenshot.

    Files land in benchmarks/shots/<label>/spotNN.tga (+ .png and .small.png). skip_intro=None skips the cutscene
    automatically on maps that need it (escape1, crypt1: otherwise the intro camera/black frames). `settle` is the
    startup wait in frames (400), `wait_frames` the wait after each teleport. `cvars` are forced at startup (latched
    ones work; max 8). `commands` run at each spot before the shot (e.g. "r_normalMapping 0" is NOT a command: use cvars)."""
    try:
        res = await _in_thread(ctx, _do_screenshot, map, spots, skip_intro, settle, cvars, label, hud, wait_frames,
                               max_width, commands)
    except RtcwError as e:
        return [json.dumps(_fail(e))]
    blocks: list[Any] = [json.dumps(res, indent=1)]
    if return_images:
        blocks += [Image(path=s["small_png"]) for s in res["shots"][:6]]
    return blocks


# ------------------------------------------------------------------ texture_coverage / console_log

def _do_coverage(map, spots, skip_intro, settle, cvars, shader_filter, tick=None):
    parsed = [core.parse_spot(s) for s in spots]
    if not parsed:
        raise RtcwError("give at least one spot")
    steps = [Step(spot=s, commands=["normalcov"], settle=20) for s in parsed]
    # normalcov reports on the NEXT rendered frame: Step waits 3 frames after each command.
    r = core.run_steps(map, steps, cvars=cvars, skip_intro=skip_intro, settle=settle, tick=tick)
    out = []
    rx = re.compile(shader_filter) if shader_filter else None
    for s, lines in zip(parsed, r["steps"]):
        cov = core.parse_normalcov(lines)
        if rx:
            cov["entries"] = [e for e in cov["entries"] if rx.search(e["shader"])]
        cov["spot"] = s
        out.append(cov)
    ok = r["completed"] and all(c["parsed"] for c in out)
    return {"ok": ok, "map": map, "skip_intro": r["skip_intro"], "seconds": r["seconds"], "spots": out,
            "warnings": r["warnings"], "errors": r["errors"],
            "statuses": "parallax = _nh found and relief active; normal map = _n only; NO NORMAL MAP = lightall surface "
                        "without any; not lightall = other shader type (sky, 2D, fx...)"}


@mcp.tool()
async def texture_coverage(map: str, spots: list[Spot], shader_filter: str | None = None,
                           skip_intro: bool | None = None, settle: int = core.DEFAULT_SETTLE,
                           cvars: dict[str, str] | None = None, ctx: Context | None = None) -> dict:
    """Run the `normalcov` console command at each spot and return the parsed table: per visible shader the surface
    count, diffuse image, and status (parallax / _nh found, parallax off / normal map / NO NORMAL MAP / not lightall
    / normals off (cvars)), plus per-status totals and the covered percentage. `shader_filter` is a regex on shader
    names. Needs a rend2 build with `normalcov` (2026-10-23+)."""
    try:
        return await _in_thread(ctx, _do_coverage, map, spots, skip_intro, settle, cvars, shader_filter)
    except RtcwError as e:
        return _fail(e)


def _do_console(map, spot, commands, skip_intro, settle, cvars, grep, max_lines, tick=None):
    cmds = [core.check_console_cmd(c) for c in commands]
    if not cmds:
        raise RtcwError("give at least one console command")
    ps = core.parse_spot(spot) if spot else None
    r = core.run_steps(map, [Step(spot=ps, commands=cmds, settle=20)], cvars=cvars, skip_intro=skip_intro,
                       settle=settle, tick=tick)
    lines = [l for l in r["steps"][0] if l.strip()]
    if grep:
        rx = re.compile(grep)
        lines = [l for l in lines if rx.search(l)]
    trunc = max(0, len(lines) - max_lines)
    return {"ok": r["completed"], "map": map, "spot": ps, "seconds": r["seconds"], "lines": lines[:max_lines],
            "truncated_lines": trunc, "warnings": r["warnings"], "errors": r["errors"]}


@mcp.tool()
async def console_log(map: str, commands: list[str], spot: Spot | None = None, grep: str | None = None,
                       max_lines: int = 200, skip_intro: bool | None = None, settle: int = core.DEFAULT_SETTLE,
                       cvars: dict[str, str] | None = None, ctx: Context | None = None) -> dict:
    """Load `map` headless, optionally teleport to `spot`, run console commands (one per entry; e.g. "viewpos",
    "gpuprof", "r_showtris 1") and return the console output they produced (optionally filtered by regex).
    quit/bind/exec/vid_restart are refused. Cvars to set at startup go in `cvars`."""
    try:
        return await _in_thread(ctx, _do_console, map, spot, commands, skip_intro, settle, cvars, grep, max_lines)
    except RtcwError as e:
        return _fail(e)


# ------------------------------------------------------------------ script wrappers: load_times, benchmark

def _run_script(args: list[str], timeout: float, tick=None, extra_env: dict | None = None) -> tuple[int, str, bool]:
    import os
    import signal
    p = subprocess.Popen(args, cwd=core.ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         start_new_session=True, env={**os.environ, **(extra_env or {})})
    t0 = time.monotonic()
    hung = False
    while True:
        try:
            out, _ = p.communicate(timeout=10)
            break
        except subprocess.TimeoutExpired:
            if tick:
                tick()
            if time.monotonic() - t0 > timeout:
                hung = True
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    out, _ = p.communicate(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
                    out, _ = p.communicate()
                break
    return p.returncode, out, hung


_LOAD_ROW = re.compile(r"^\s+(\S+)\s+(\S+)\s+([\d.]+)ms\s+(\d+)\s+([\d.]+)ms@(\S+)\s+([\d.]+)ms\s+(\d+)\s+(PASS|FAIL)")
_LOAD_GAP = re.compile(r"^\s+gap\s+([\d.]+) ms @ (\S+)\s+t=([\d.]+) ms\s+hint=(\S+)")


def parse_load_test(text: str) -> dict:
    maps: list[dict] = []
    for ln in text.splitlines():
        if ln.startswith(">> "):
            maps.append({"name": ln[3:].strip(), "loads": [], "notes": []})
        elif (m := _LOAD_ROW.match(ln)) and maps:
            maps[-1]["loads"].append({"map": m[1], "why": m[2], "total_ms": float(m[3]), "frames": int(m[4]),
                                      "maxgap_ms": float(m[5]), "maxgap_at": m[6], "p95_ms": float(m[7]),
                                      "over33": int(m[8]), "pass": m[9] == "PASS", "gaps": []})
        elif (m := _LOAD_GAP.match(ln)) and maps and maps[-1]["loads"]:
            maps[-1]["loads"][-1]["gaps"].append({"ms": float(m[1]), "at": m[2], "t_ms": float(m[3]), "hint": m[4]})
        elif ("FAIL" in ln or "HUNG" in ln) and maps:
            maps[-1]["notes"].append(ln.strip())
    return {"maps": maps, "passed": "load-test: PASS" in text}


def _do_load_times(maps, level_change, profile_level, tick=None):
    names = [core.check_map(m) for m in maps]
    if not names:
        raise RtcwError("give at least one map")
    with core.exclusive("run load-test"):
        t0 = time.monotonic()
        rc, out, hung = _run_script(["scripts/load-test.sh", "--maps", " ".join(names), "--profile-level",
                                     str(profile_level), *(["--level-change"] if level_change else [])],
                                    timeout=330 * len(names) + 60, tick=tick)
    res = parse_load_test(out)
    res.update({"ok": rc == 0 and bool(res["maps"]), "exit_code": rc, "seconds": round(time.monotonic() - t0, 1),
                "raw_logs": "benchmarks/load-<stamp>-<map>.log (not committed)"})
    if hung:
        res["warnings"] = ["HUNG: the script was terminated after its long timeout"]
    if not res["maps"]:
        res["output_tail"] = _tail(out)
    return res


@mcp.tool()
async def load_times(maps: list[str], level_change: bool = False, profile_level: int = 1,
                     ctx: Context | None = None) -> dict:
    """Wrap scripts/load-test.sh: load each map headless with the loading-screen profiler and report total time,
    presented frames, max present gap, p95 and the number of gaps > 33 ms (PASS = none), with the gap list
    (`profile_level` 2 adds stage marks in the raw log). ~10 s per map."""
    try:
        return await _in_thread(ctx, _do_load_times, maps, level_change, profile_level)
    except RtcwError as e:
        return _fail(e)


_BENCH_RUN = re.compile(r"frames=(\d+)\s+([\d.]+)s\s+avg ([\d.]+) fps\s+1%low ([\d.]+) fps\s+P99 ([\d.]+) ms\s+max ([\d.]+) ms\s+hitches (\d+)")
_BENCH_SUM = re.compile(r"avg ([\d.]+) fps \| 1% low ([\d.]+) fps \| P99 ([\d.]+) ms")
_SPIN_ROW = re.compile(r"^(STILL|YAW_\d+)\s+GPU\s+([\d.]+) ms\s+x([\d.]+)(\s+<-- FAIL)?")


_GPU_HEAD = re.compile(r"gpu: frames=(\d+) gpu_avg_ms=([\d.]+) gpu_max_ms=([\d.]+)")
_GPU_ROW = re.compile(r"gpu: (\S.*?)\s+avg_ms=\s*([\d.]+)\s+pct=\s*([\d.]+)\s+max_ms=\s*([\d.]+)\s+hit=\s*([\d.]+)%")


def parse_gpuprof(text: str) -> list[dict]:
    """The `bench.sh --gpuprof` tables, one per run: {frames, gpu_avg_ms, gpu_max_ms, passes: [...]}."""
    runs: list[dict] = []
    for ln in text.splitlines():
        if (m := _GPU_HEAD.search(ln)):
            runs.append({"frames": int(m[1]), "gpu_avg_ms": float(m[2]), "gpu_max_ms": float(m[3]), "passes": []})
        elif (m := _GPU_ROW.search(ln)) and runs:
            runs[-1]["passes"].append({"pass": m[1], "avg_ms": float(m[2]), "pct": float(m[3]),
                                       "max_ms": float(m[4]), "hit_pct": float(m[5])})
    return runs


def parse_bench(text: str) -> dict:
    runs = [{"frames": int(m[1]), "seconds": float(m[2]), "avg_fps": float(m[3]), "low1_fps": float(m[4]),
             "p99_ms": float(m[5]), "max_ms": float(m[6]), "hitches": int(m[7])}
            for m in _BENCH_RUN.finditer(text)]
    s = _BENCH_SUM.search(text)
    res: dict = {"runs": runs}
    if (g := parse_gpuprof(text)):
        res["gpu_passes_last_run"] = g[-1]
    if s:
        res["median"] = {"avg_fps": float(s[1]), "low1_fps": float(s[2]), "p99_ms": float(s[3])}
    if (m := re.search(r"cfg: (.*)", text)):
        res["cfg"] = m[1].strip()
    return res


def parse_spin(text: str) -> dict:
    rows = {m[1]: {"gpu_ms": float(m[2]), "ratio": float(m[3]), "fail": bool(m[4])}
            for ln in text.splitlines() if (m := _SPIN_ROW.match(ln))}
    return {"rows": rows}


def _do_benchmark(kind, cvars, runs, label, max_ratio, gpuprof, tick=None):
    cv = core.check_cvars(cvars)
    if not re.match(r"^[\w.\-]+$", label):
        raise RtcwError("label: letters, digits, . _ - only")
    with core.exclusive(f"run the {kind} benchmark") as warnings:
        t0 = time.monotonic()
        if kind == "normal":
            args = ["scripts/bench.sh", "--label", label, "--runs", str(runs)] + (["--gpuprof"] if gpuprof else [])
            for k, v in cv.items():
                args += ["--set", k, v]
            rc, out, hung = _run_script(args, timeout=240 * runs + 120, tick=tick)
            res = parse_bench(out)
            res["ok"] = rc == 0 and bool(res["runs"])
        else:
            if cv:
                raise RtcwError("spin-test.sh does not accept cvars; run kind=normal for A/B with cvars")
            rc, out, hung = _run_script(["scripts/spin-test.sh", "--max-ratio", str(max_ratio)], timeout=420, tick=tick)
            res = parse_spin(out)
            res["ok"] = bool(res["rows"])
            res["spin_pass"] = rc == 0
    res.update({"kind": kind, "exit_code": rc, "seconds": round(time.monotonic() - t0, 1), "warnings": warnings})
    if hung:
        res["warnings"].append("HUNG: the script was terminated after its long timeout")
    if not res["ok"]:
        res["output_tail"] = _tail(out)
    return res


@mcp.tool()
async def benchmark(kind: str = "normal", cvars: dict[str, str] | None = None, runs: int = 3,
                    label: str = "mcp", max_ratio: float = 1.25, gpuprof: bool = False, ctx: Context | None = None) -> dict:
    """Run a benchmark off-screen. kind="normal": scripts/bench.sh (replays the benchmark demo `runs` times, run 1 is
    warm-up) -> avg fps, 1% low, P99, hitches per run and the median; appended to benchmarks/results.csv. `cvars` are
    forced via --set. gpuprof=true adds r_gpuProfile 1 and returns the per-pass GPU ms table of the last run
    (`gpu_passes_last_run`: avg ms, % of GPU time, max, hit %; the table of every run is saved as
    benchmarks/<stamp>-<label>-runN.gpuprof.txt). kind="spin": scripts/spin-test.sh -> GPU ms for still vs turning views and PASS/FAIL against
    `max_ratio`. Always headless; ~1-5 minutes."""
    if kind not in ("normal", "spin"):
        return _fail(RtcwError("kind must be 'normal' or 'spin'"))
    try:
        return await _in_thread(ctx, _do_benchmark, kind, cvars, runs, label, max_ratio, gpuprof)
    except RtcwError as e:
        return _fail(e)


# ------------------------------------------------------------------ compare_shots

def _resolve_shots(ref: str) -> list[Path]:
    """A file, or a label under benchmarks/shots/ (all its spot*.tga / shot*.tga), or a directory."""
    p = Path(ref)
    if not p.is_absolute() and not p.exists():
        p = core.SHOTS_DIR / ref
    if p.is_file():
        return [p]
    if p.is_dir():
        files = sorted(list(p.glob("spot*.tga")) + list(p.glob("shot*.tga")))
        if files:
            return files
    raise RtcwError(f"no screenshots found for {ref!r} (file, directory or label in benchmarks/shots/)")


def compare_images(a: Path, b: Path, out_png: Path, max_width: int = 1920) -> dict:
    import numpy as np
    from PIL import Image
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if ia.size != ib.size:
        return {"a": str(a), "b": str(b), "error": f"size differs {ia.size} vs {ib.size}"}
    xa, xb = np.asarray(ia, dtype=np.int16), np.asarray(ib, dtype=np.int16)
    d = np.abs(xa - xb)
    px = d.max(axis=2)
    diff = Image.fromarray(np.clip(px * 16, 0, 255).astype(np.uint8)).convert("RGB")
    w, h = ia.size
    sheet = Image.new("RGB", (w * 3, h))
    sheet.paste(ia, (0, 0)); sheet.paste(ib, (w, 0)); sheet.paste(diff, (2 * w, 0))
    if sheet.width > max_width:
        sheet = sheet.resize((max_width, round(sheet.height * max_width / sheet.width)), Image.LANCZOS)
    sheet.save(out_png, "PNG")
    return {"a": str(a), "b": str(b), "differing_px_pct": round(100.0 * np.count_nonzero(px) / px.size, 3),
            "over2_pct": round(100.0 * np.count_nonzero(px > 2) / px.size, 3), "max_diff": int(px.max()),
            "mean_diff": round(float(d.mean()), 4), "side_by_side": str(out_png)}


def _do_compare(a, b, max_width):
    fa, fb = _resolve_shots(a), _resolve_shots(b)
    if len(fa) == 1 and len(fb) == 1:
        pairs = [(fa[0], fb[0])]
    else:
        index = {p.name: p for p in fb}
        pairs = [(p, index[p.name]) for p in fa if p.name in index]
        if not pairs:
            raise RtcwError("no files with matching names (spot01.tga ...) in both sets")
    out_dir = core.SHOTS_DIR / "compare"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    res = [compare_images(x, y, out_dir / f"cmp-{stamp}-{i:02d}.png", max_width) for i, (x, y) in enumerate(pairs, 1)]
    return {"ok": True, "pairs": res}


@mcp.tool()
async def compare_shots(a: str, b: str, max_width: int = 1920, return_images: bool = True) -> list:
    """Compare two screenshots, or two sets (labels under benchmarks/shots/, matched by file name). Per pair: share of
    differing pixels, >2 levels, max and mean difference, plus a PNG "A | B | diff x16". Note: scripts/shots-diff.py
    only globs shot*.tga (timedemo shots); this tool also handles spotNN.tga from `screenshot`. No game is launched."""
    try:
        res = await asyncio.to_thread(_do_compare, a, b, max_width)
    except (RtcwError, OSError) as e:
        return [json.dumps(_fail(e))]
    blocks: list[Any] = [json.dumps(res, indent=1)]
    if return_images:
        blocks += [Image(path=p["side_by_side"]) for p in res["pairs"][:4] if "side_by_side" in p]
    return blocks


# ------------------------------------------------------------------ build

_DIAG = re.compile(r"^(?P<loc>\S+?:\d+(?::\d+)?): (?P<kind>warning|error|fatal error): (?P<msg>.*)$")


def summarize_build(text: str) -> dict:
    warnings, errors = [], []
    for ln in text.splitlines():
        if (m := _DIAG.match(ln.strip())):
            (errors if "error" in m["kind"] else warnings).append(f'{m["loc"]}: {m["msg"]}')
    return {"warning_count": len(warnings), "error_count": len(errors),
            "warnings": sorted(set(warnings))[:25], "errors": sorted(set(errors))[:25]}


def _do_build(game_only, install, tick=None):
    args = ["scripts/build.sh"] + (["--game-only"] if game_only else []) + (["--install"] if install else [])
    with core.exclusive("build", check_build=True) as warnings:
        t0 = time.monotonic()
        rc, out, hung = _run_script(args, timeout=1800, tick=tick)
    res = summarize_build(out)
    res.update({"ok": rc == 0, "exit_code": rc, "seconds": round(time.monotonic() - t0, 1), "command": " ".join(args),
                "warnings_notes": warnings})
    if rc != 0:
        res["output_tail"] = _tail(out, 30)
    return res


@mcp.tool()
async def build(game_only: bool = True, install: bool = True, ctx: Context | None = None) -> dict:
    """Run scripts/build.sh [--game-only] [--install] (game_only=False also rebuilds the engine/renderer; install
    must stay true or run/ keeps stale modules). Returns exit code, warning/error counts and the first diagnostics,
    and the output tail only on failure. Refuses while the game or another build is running."""
    try:
        return await _in_thread(ctx, _do_build, game_only, install)
    except RtcwError as e:
        return _fail(e)


# ------------------------------------------------------------------ status, maps, spots

@mcp.tool()
def game_status() -> dict:
    """Is a game / build / texture bake running right now (so a tool call would be refused), and is the lock held?"""
    import fcntl, os
    held = False
    try:
        fd = os.open(core.LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            held = True
        os.close(fd)
    except OSError:
        pass
    eng = core.ROOT / "run" / "iowolfsp.x86_64"
    return {"game_running": core.game_processes(), "build_running": core.build_processes(),
            "bake_running": core.bake_processes(), "lock_held_by_rtcw_mcp": held,
            "engine_installed": eng.is_file(), "engine_mtime": time.ctime(eng.stat().st_mtime) if eng.is_file() else None}


@mcp.tool()
def list_maps() -> dict:
    """Maps found in run/main/*.pk3 (usable as `map`), and which of them get the automatic intro skip."""
    maps = core.list_maps()
    return {"maps": maps, "auto_intro_skip": sorted(core.INTRO_SKIP_MAPS)}


@mcp.tool()
def known_spots(map: str | None = None) -> dict:
    """Known camera spots: benchmarks/spots-<map>.txt files plus a few documented ones (trainyard wall, crypt1,
    escape1 spin view). Each is 'x y z yaw pitch'."""
    files = core.spots_from_files()
    allspots = {m: [{"name": "benchmarks/spots-%s.txt" % m, "spot": s} for s in v] for m, v in files.items()}
    for m, v in core.KNOWN_SPOTS.items():
        allspots.setdefault(m, []).extend(v)
    return {"spots": allspots.get(map, []) if map else allspots}


@mcp.resource("rtcw://spots")
def spots_resource() -> str:
    return json.dumps(known_spots(), indent=1)


@mcp.resource("rtcw://gotchas")
def gotchas_resource() -> str:
    return (Path(__file__).parent / "README.md").read_text()


if __name__ == "__main__":
    mcp.run()
