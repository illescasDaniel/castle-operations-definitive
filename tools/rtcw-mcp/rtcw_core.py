"""Core logic for the rtcw-mcp server: spot parsing, cfg building, log parsing, the locked headless runner.

No MCP imports here, so everything is unit-testable without launching the game (see tests/).
The runner follows scripts/shot-at.sh: one-line console script via +exec, headless gamescope,
wolfconfig.cfg backed up and restored, clean `quit` at the end.
"""
from __future__ import annotations

import fcntl
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Sequence

ROOT = Path(os.environ.get("RTCW_ROOT", Path(__file__).resolve().parents[2]))
HOME_CFG = ROOT / "run" / "home" / "codmod"
CONSOLE_LOG = HOME_CFG / "rtcwconsole.log"
SHOTS_DIR = ROOT / "benchmarks" / "shots"
LOCK_PATH = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir())) / "rtcw-mcp.lock"

# Maps whose first seconds are a scripted cutscene; `cmd cameraInterrupt` skips it. Without it escape1 shows
# the intro camera and crypt1 screenshots come out black.
INTRO_SKIP_MAPS = {"escape1", "crypt1"}
INTRO_SKIP_CMD = "cmd cameraInterrupt"

# Console-script waits count frames (not ms). A scripted quit during a map load segfaults, so waits are generous.
DEFAULT_SETTLE = 400

NORMALCOV_STATUSES = (
    "not lightall", "NO NORMAL MAP", "normal map", "_nh found, parallax off", "parallax", "normals off (cvars)",
)

_CVAR_NAME = re.compile(r"^[A-Za-z_][\w.]*$")
_CVAR_VALUE = re.compile(r"^[\w.+\-/]+$")
_MAP_NAME = re.compile(r"^[A-Za-z0-9_]+$")
MAX_STARTUP_CVARS = 8  # the engine drops "+" commands beyond 32 and run.sh already uses ~27 args' worth


class RtcwError(RuntimeError):
    """A refusal or failure with a message meant for the agent."""


# ---------------------------------------------------------------- input validation

def parse_spot(spot: str | Sequence[float]) -> str:
    """'setviewpos -737,3 469,2 107,4 -86,7 15,8' | 'x y z yaw pitch' | [x,y,z,yaw,pitch] -> 'x y z yaw pitch'."""
    if isinstance(spot, str):
        s = spot.strip()
        if s.startswith("setviewpos"):
            s = s[len("setviewpos"):]
        parts = s.replace(",", ".").split()
    else:
        parts = [str(v) for v in spot]
    if len(parts) == 4:  # "x y z yaw": pitch defaults to level
        parts.append("0")
    if len(parts) != 5:
        raise RtcwError(f"spot must be 'x y z yaw pitch' (got {spot!r}); `viewpos` in the console prints one")
    try:
        [float(p) for p in parts]
    except ValueError:
        raise RtcwError(f"spot has a non-numeric field: {spot!r}") from None
    return " ".join(parts)


def check_map(name: str) -> str:
    if not _MAP_NAME.match(name):
        raise RtcwError(f"bad map name {name!r}")
    return name


def check_cvars(cvars: dict[str, str | int | float] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in (cvars or {}).items():
        if not _CVAR_NAME.match(k):
            raise RtcwError(f"bad cvar name {k!r}")
        sv = str(v)
        if not _CVAR_VALUE.match(sv):
            raise RtcwError(f"cvar {k} value {sv!r} not allowed (letters, digits, . + - _ / only)")
        out[k] = sv
    if len(out) > MAX_STARTUP_CVARS:
        raise RtcwError(f"at most {MAX_STARTUP_CVARS} cvars per run (engine drops startup commands beyond 32)")
    return out


def check_console_cmd(cmd: str) -> str:
    c = cmd.strip()
    if not c or ";" in c or "\n" in c:
        raise RtcwError(f"one console command per entry, no ';' or newlines: {cmd!r}")
    if re.match(r"(?i)^(quit|exit|disconnect|vid_restart|condump|writeconfig|unbind|bind|exec)\b", c):
        raise RtcwError(f"console command not allowed here (would end the run or touch the config): {cmd!r}")
    return c


# ---------------------------------------------------------------- cfg building

@dataclass
class Step:
    spot: str | None = None            # "x y z yaw pitch"
    commands: list[str] = field(default_factory=list)  # run after arriving, in order
    screenshot: str | None = None      # base name (no extension); lands in run/home/codmod/screenshots/
    settle: int = 20                   # frames to wait after teleport/commands


def mark(i: int, what: str) -> str:
    return f"MCPMARK {what} {i}"


def build_cfg(steps: Sequence[Step], *, settle: int = DEFAULT_SETTLE, skip_intro: bool = False,
              hud: bool = False, pre: Sequence[str] = ()) -> str:
    """One-line console script (the engine's `wait N` defers the rest of the buffer by N frames)."""
    parts = [f"set con_notifytime -1", f"wait {settle}", "uiclick 612 466", "wait 5", "uiclick", "wait 30", "god", "notarget",
             "set cg_drawGun 0"]
    if not hud:
        parts.append("set cg_draw2D 0")
    if skip_intro:
        parts += [INTRO_SKIP_CMD, "wait 60"]
    parts += list(pre)
    for i, st in enumerate(steps, 1):
        parts.append(f"echo {mark(i, 'BEGIN')}")
        if st.spot:
            parts.append(f"setviewpos {st.spot}")
            parts.append(f"wait {st.settle}")
        for c in st.commands:
            parts.append(c)
            parts.append("wait 3")
        if st.screenshot:
            parts.append(f"screenshot {st.screenshot}")
            parts.append("wait 5")
        parts.append(f"echo {mark(i, 'END')}")
    parts += ["wait 5", "quit"]
    return "; ".join(parts)


# ---------------------------------------------------------------- log parsing

def split_by_marks(lines: Sequence[str], n: int) -> list[list[str]]:
    """Lines between `MCPMARK BEGIN i` and `MCPMARK END i`, one list per step (empty if the marks are missing)."""
    out: list[list[str]] = [[] for _ in range(n)]
    cur: int | None = None
    for ln in lines:
        m = re.search(r"MCPMARK (BEGIN|END) (\d+)\s*$", ln)
        if m:
            idx = int(m.group(2)) - 1
            if m.group(1) == "BEGIN" and 0 <= idx < n:
                cur = idx
            else:
                cur = None
            continue
        if cur is not None:
            out[cur].append(ln)
    return out


_COV_ROW = re.compile(
    r"^\s*(\d+)\s+(\S+)\s+(\S+)\s+(" + "|".join(re.escape(s) for s in NORMALCOV_STATUSES) + r")\s*$")
_COV_HEAD = re.compile(r"normalcov: (\d+) surfaces, (\d+) shaders")
_COV_TOTAL = re.compile(r"^\s*(" + "|".join(re.escape(s) for s in NORMALCOV_STATUSES) + r")\s+(\d+) surfaces\s*$")
_COV_FINAL = re.compile(r"normalcov: (\d+)/(\d+) lightall surfaces have a normal map \(([\d.]+)%\)")
_COV_MORE = re.compile(r"\.\.\. (\d+) more shaders")


def parse_normalcov(lines: Sequence[str]) -> dict:
    """Parse the output of the `normalcov` console command (rend2 R_NormalCovReport)."""
    res: dict = {"surfaces": None, "shaders": None, "entries": [], "totals": {}, "more_shaders": 0,
                 "covered": None, "lightall": None, "covered_pct": None}
    for ln in lines:
        if (m := _COV_HEAD.search(ln)):
            res["surfaces"], res["shaders"] = int(m[1]), int(m[2])
        elif (m := _COV_FINAL.search(ln)):
            res["covered"], res["lightall"], res["covered_pct"] = int(m[1]), int(m[2]), float(m[3])
        elif (m := _COV_MORE.search(ln)):
            res["more_shaders"] = int(m[1])
        elif (m := _COV_TOTAL.match(ln)):
            res["totals"][m[1]] = int(m[2])
        elif (m := _COV_ROW.match(ln)):
            res["entries"].append({"count": int(m[1]), "shader": m[2],
                                   "image": None if m[3] == "-" else m[3], "status": m[4]})
    res["parsed"] = res["surfaces"] is not None
    return res


def read_new_lines(path: Path, offset: int = 0) -> list[str]:
    try:
        data = path.read_bytes()[offset:]
    except OSError:
        return []
    return [l.rstrip("\r") for l in data.decode("utf-8", "replace").split("\n")]


_ERR_PATTERNS = re.compile(r"(?i)(^ERROR|Com_Error|segmentation|Sys_Error|could not find map|Couldn't load|crash)")


def interesting_errors(lines: Sequence[str], limit: int = 10) -> list[str]:
    return [l.strip() for l in lines if _ERR_PATTERNS.search(l)][:limit]


# ---------------------------------------------------------------- process guards, lock

def pgrep(pattern: str) -> list[str]:
    try:
        out = subprocess.run(["pgrep", "-af", pattern], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    me = str(os.getpid())
    return [l for l in out.splitlines() if l.split(" ", 1)[0] != me]


def game_processes() -> list[str]:
    return pgrep(r"iowolfsp\.x86_64")


def bake_processes() -> list[str]:
    return [l for l in pgrep(r"height_bake\.py") if "multiprocessing" not in l][:3]


def build_processes() -> list[str]:
    return pgrep(r"scripts/build\.sh|make .*iortcw")


@contextmanager
def exclusive(what: str, *, check_game: bool = True, check_build: bool = True) -> Iterator[list[str]]:
    """Single game instance at a time: file lock + refuse if an iowolfsp (maybe the user's) is already running.

    Yields a list of warnings (e.g. a texture bake running concurrently)."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RtcwError(f"another rtcw-mcp tool is already running a game/build ({LOCK_PATH}); try again later") from None
        if check_game and (g := game_processes()):
            raise RtcwError(f"refusing to {what}: an iowolfsp process is already running (maybe you are playing): {g[0][:160]}")
        if check_build and (b := build_processes()):
            raise RtcwError(f"refusing to {what}: a build is running ({b[0][:120]}); run/ would be half-installed")
        warnings = []
        if (bk := bake_processes()):
            warnings.append("a height_bake.py run is active; the game may load a half-written pack and results may "
                            "change once it finishes")
        yield warnings
    finally:
        os.close(fd)  # releases the flock


@contextmanager
def wolfconfig_guard() -> Iterator[None]:
    """Back up the user's wolfconfig.cfg and restore it afterwards (a scripted run saves its cvars on quit)."""
    cfg = HOME_CFG / "wolfconfig.cfg"
    saved = None
    if cfg.is_file() and cfg.stat().st_size > 0:
        saved = Path(tempfile.mkstemp(prefix="wolfconfig-", suffix=".bak")[1])
        shutil.copy2(cfg, saved)
    try:
        yield
    finally:
        if saved is not None:
            shutil.copy2(saved, cfg)
            saved.unlink(missing_ok=True)


# ---------------------------------------------------------------- the runner

@dataclass
class RunResult:
    returncode: int | None
    seconds: float
    log_lines: list[str]
    killed_hung: bool = False
    timed_out: bool = False


Launcher = Callable[[Sequence[str], dict, float, "Callable[[], None] | None"], RunResult]


def headless_cmd(map_name: str, cfg_name: str, width: int, height: int, extra: Sequence[str] = ()) -> list[str]:
    return ["gamescope", "--backend", "headless", "-W", str(width), "-H", str(height), "--",
            str(ROOT / "scripts" / "run.sh"), "--windowed", f"{width}x{height}",
            "+spdevmap", map_name, "+exec", cfg_name, *extra]


def real_launcher(cmd: Sequence[str], env: dict, timeout: float, tick: Callable[[], None] | None) -> RunResult:
    """Run the game in its own process group. Only if the timeout fires (a genuinely hung run) is it terminated,
    SIGTERM first, SIGKILL as a last resort, and the result says so."""
    CONSOLE_LOG.parent.mkdir(parents=True, exist_ok=True)
    CONSOLE_LOG.write_bytes(b"")  # as the other scripts do: the log then holds exactly this run
    t0 = time.monotonic()
    p = subprocess.Popen(list(cmd), env={**os.environ, **env}, cwd=ROOT, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    killed = timed_out = False
    last_tick = t0
    while True:
        try:
            p.wait(timeout=2)
            break
        except subprocess.TimeoutExpired:
            now = time.monotonic()
            if tick and now - last_tick >= 10:
                tick()
                last_tick = now
            if now - t0 > timeout:
                timed_out = True
                for sig, grace in ((signal.SIGTERM, 20), (signal.SIGKILL, 10)):
                    try:
                        os.killpg(p.pid, sig)
                    except ProcessLookupError:
                        break
                    killed = True
                    try:
                        p.wait(timeout=grace)
                        break
                    except subprocess.TimeoutExpired:
                        continue
                break
    return RunResult(p.returncode, time.monotonic() - t0, read_new_lines(CONSOLE_LOG), killed, timed_out)


def run_steps(map_name: str, steps: Sequence[Step], *, cvars: dict | None = None, skip_intro: bool | None = None,
              settle: int = DEFAULT_SETTLE, hud: bool = False, pre: Sequence[str] = (),
              timeout: float = 600, width: int = 1920, height: int = 1200,
              launcher: Launcher = real_launcher, tick: Callable[[], None] | None = None) -> dict:
    """Load `map_name` headless, run the steps, quit cleanly. Returns per-step log lines and run metadata."""
    check_map(map_name)
    cv = check_cvars(cvars)
    pre = [check_console_cmd(c) for c in pre]
    if skip_intro is None:
        skip_intro = map_name in INTRO_SKIP_MAPS
    cfg_name = f"rtcwmcp-{os.getpid()}.cfg"
    cfg_path = HOME_CFG / cfg_name
    cfg = build_cfg(steps, settle=settle, skip_intro=skip_intro, hud=hud, pre=pre)
    shots_tmp = HOME_CFG / "screenshots"
    with exclusive(f"run {map_name}") as warnings, wolfconfig_guard():
        shots_tmp.mkdir(parents=True, exist_ok=True)
        for f in shots_tmp.glob("codmod_mcp_*"):
            f.unlink(missing_ok=True)
        cfg_path.write_text(cfg + "\n")
        env = {"RTCW_STARTUP_SETS": " ".join(f"{k}={v}" for k, v in cv.items())}
        try:
            r = launcher(headless_cmd(map_name, cfg_name, width, height), env, timeout, tick)
        finally:
            cfg_path.unlink(missing_ok=True)
    per_step = split_by_marks(r.log_lines, len(steps))
    out = {
        "map": map_name, "skip_intro": skip_intro, "seconds": round(r.seconds, 1), "returncode": r.returncode,
        "completed": f"MCPMARK END {len(steps)}" in "\n".join(r.log_lines),
        "steps": per_step, "warnings": warnings, "errors": interesting_errors(r.log_lines),
        "log_lines": len(r.log_lines),
    }
    if r.timed_out:
        out["warnings"].append(f"HUNG: no clean exit after {timeout:.0f} s, the process group was terminated "
                               f"(SIGTERM{', then SIGKILL' if r.killed_hung else ''}); the next launch may show the "
                               "'safe options' popup")
    return out


# ---------------------------------------------------------------- misc helpers

def list_maps() -> list[str]:
    names: set[str] = set()
    for pk in sorted((ROOT / "run" / "main").glob("*.pk3")):
        try:
            with zipfile.ZipFile(pk) as z:
                for n in z.namelist():
                    if n.startswith("maps/") and n.endswith(".bsp"):
                        names.add(n[5:-4])
        except (OSError, zipfile.BadZipFile):
            continue
    return sorted(names)


def spots_from_files() -> dict[str, list[str]]:
    """benchmarks/spots-<map>.txt -> {map: [spot, ...]} (comment lines ignored)."""
    out: dict[str, list[str]] = {}
    for f in sorted((ROOT / "benchmarks").glob("spots-*.txt")):
        spots = []
        for l in f.read_text().splitlines():
            if l.strip() and not l.startswith("#"):
                try:
                    spots.append(parse_spot(l))
                except RtcwError:
                    pass
        out[f.stem[len("spots-"):]] = spots
    return out


KNOWN_SPOTS: dict[str, list[dict]] = {
    "trainyard": [
        {"name": "dark stone wall (parallax expected on town_wall/town_c22a1burn)",
         "spot": "-1012.1 481.6 88.1 -143.3 9.5"},
        {"name": "viewpos from normals-coverage-plan (concrete wall + stone corner)", "spot": "-1012 481 128 0 0"},
    ],
    "crypt1": [{"name": "normals-coverage check spot (needs intro skip)", "spot": "-201 1593 520 0 0"}],
    "escape1": [{"name": "spin-test wide view after the intro cutscene", "spot": "1808.0 1600.0 -759.9 0 0"}],
}


def downscale_png(src: Path, dst: Path, max_width: int) -> Path:
    from PIL import Image
    im = Image.open(src).convert("RGB")
    if im.width > max_width:
        im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
    im.save(dst, "PNG")
    return dst
