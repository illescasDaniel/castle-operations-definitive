#!/usr/bin/env python3
"""AP stability scenario: repeatable load square wave for `r_frameWarp 2` (Smooth / "AP") plus an analyzer.

Subcommands
  args      print the exact rtcw-mcp console_log arguments (JSON) for the scenario
  analyze   parse a saved console log (apstats output, optional timeline / dump) and print a pass/fail summary
  smi       log nvidia-smi GPU clocks to a CSV (run it in the background next to the game), or summarise one

Typical use (an agent):
  scripts/ap-scenario.py args > /tmp/ap-args.json        # feed "cvars", "commands", "map", "spot" to mcp__rtcw__console_log
  # save the tool's "lines" (one per line) to /tmp/ap.log, optionally the engine's apdump.txt is read via --dump
  scripts/ap-scenario.py analyze /tmp/ap.log --baseline benchmarks/ap-baseline.json
  scripts/ap-scenario.py analyze /tmp/ap.log --save-baseline benchmarks/ap-baseline.json

Docs: docs/frame-warp.md, section "AP stability scenario". Stdlib only.
"""
import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time

MAP = "escape1"
SPOT = "1808 1600 -759.9 0 0"
# exactly 8 startup cvars (MCP limit). Add r_gpuProfile 1 only by swapping one out for a calibration run.
CVARS = {
    "r_frameWarp": "2", "r_frameWarpAp": "2", "r_frameWarpMesh": "3", "r_aa": "8",
    "com_maxfps": "120", "com_maxfpsGpuSync": "2", "com_maxfpsMode": "0", "r_vsync": "0",
}
# Load levels. Each is a list of console commands run when the phase starts (no startup-cvar slots used).
# Calibrated at 1920x1200 headless on escape1 (see docs): LIGHT ~5.1 ms GPU busy per real frame (defaults, spot view);
# HEAVY ~8.3 ms = light + the dev cvar r_gpuLoad (microseconds of synthetic GPU work per real frame, self-calibrating).
GPU_LOAD_US = 3200
LEVELS = {
    "light": ["set r_gpuLoad 0", "set r_sunShadowCascadeUpdate 0", "setviewpos 1808 1600 -759.9 0 0"],
    "heavy": ["set r_gpuLoad %d" % GPU_LOAD_US, "set r_sunShadowCascadeUpdate 0", "setviewpos 1808 1600 -759.9 0 0"],
}
# `wait N` counts presents (frames incl. warp presents): about 233 per second at slot rate 233.
WAIT_PER_S = 233
THRESH = {
    "changes_per_100s": 3.0,     # downs + ups
    "p5_vs_median": 0.9,         # 250 ms bucket distinct/s: P5 >= 0.9 x median
}


def scenario(duration_s=100, period_s=10, warm_s=4, hz=233):
    """Return the console command list: warm-up, then alternating light/heavy phases, snapshots between."""
    w = lambda s: "wait %d" % max(1, int(s * WAIT_PER_S))
    cmds = ["set r_frameWarpHz %d" % hz, "echo APSC load light"] + LEVELS["light"] + [w(warm_s + 4)]
    cmds += ["apstats reset", "apstats", "echo APSC start"]    # snapshot: downs/ups/misses baselines
    t, phase = 0, "heavy"
    while t < duration_s:
        cmds += ["echo APSC load %s" % phase] + LEVELS[phase] + [w(period_s), "apstats", "echo APSC end %s" % phase]
        t += period_s
        phase = "light" if phase == "heavy" else "heavy"
    cmds += ["apstats timeline 140", "apstats dump"]
    return cmds


def cmd_args(a):
    cmds = scenario(a.duration, a.period, hz=a.hz)
    out = {
        "map": MAP, "spot": SPOT, "cvars": CVARS, "commands": cmds,
        "grep": r"codmod ap:|^AP |^ *[0-9]+\.[0-9]+ S=|APSC|apstats|slot rate|AP delivered|frame warp AP",
        "max_lines": 400,
        "notes": "Save the returned lines to a file and run: scripts/ap-scenario.py analyze FILE [--dump run/home/codmod/apdump.txt]. "
                 "Wait counts presents, so wall time ~ duration (heavy phases run fewer real frames). Never use timescale 0.",
    }
    print(json.dumps(out, indent=1))


# ------------------------------------------------------------------ parsing

KV = re.compile(r"(\w+)=([^\s]+)")


def num(s):
    try:
        return float(s)
    except ValueError:
        return s


def parse_log(text):
    """Returns (snapshots, timeline). Snapshot = {'phase': tag, 'kv': {...}, 'head': {...}}."""
    snaps, tl, tag = [], [], None
    head = {}
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"APSC (.*)", line)
        if m:
            tag = m.group(1)
            if (tag == "start" or tag.startswith("end ")) and snaps:
                snaps[-1]["tag"] = tag      # start/end markers follow the apstats snapshot they label
            continue
        if line.startswith("AP running") or line.startswith("AP NOT running"):
            head = {k: int(v) for k, v in re.findall(r"(misses|downs|probes|kept|reverts|present fails) (\d+)", line.replace("present fails", "present_fails"))} if False else {}
            for key, pat in (("misses", r"misses (\d+)"), ("downs", r"downs (\d+)"), ("probes", r"probes (\d+)"),
                             ("kept", r"kept (\d+)"), ("reverts", r"reverts (\d+)")):
                mm = re.search(pat, line)
                if mm:
                    head[key] = int(mm.group(1))
            continue
        if "codmod ap:" in line:
            kv = {k: num(v) for k, v in KV.findall(line.split("codmod ap:", 1)[1])}
            snaps.append({"tag": None, "kv": kv, "head": head})
            head = {}
            continue
        m = re.match(r"([0-9]+\.[0-9]+) S=(\d+) dist=(\d+) warps=(\d+) reals=(\d+) decl=\S+ busy=([\d.]+)/(\d+) miss=(\d+) sleeps=(\d+) trial=(\d+)", line)
        if m:
            g = m.groups()
            tl.append({"t": float(g[0]), "slot": int(g[1]), "dist": int(g[2]), "warps": int(g[3]), "reals": int(g[4]),
                       "busy": float(g[5]), "busymax": int(g[6]), "miss": int(g[7]), "sleeps": int(g[8]), "trial": int(g[9])})
    return snaps, tl


def parse_dump(path):
    """apdump.txt: timeline rows + presents sections. Returns (timeline, present intervals us (GPU-completion), swap intervals)."""
    text = open(path, errors="replace").read()
    _, tl = parse_log(text)
    series, cur = {}, None
    for line in text.splitlines():
        if line.startswith("# presents"):
            cur = "swap" if "swap-return" in line else "gpu"
            series[cur] = []
            continue
        if cur and not line.startswith("#"):
            p = line.split()
            if len(p) == 3:
                try:
                    series[cur].append(int(p[2]))
                except ValueError:
                    pass
    for k in series:
        series[k] = series[k][1:]   # first row has no previous present
    return tl, series.get("gpu", []), series.get("swap", [])


def pct(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, int(round((len(s) - 1) * p / 100.0)))]


def fmt(x, d=1):
    return "n/a" if x != x else ("%.*f" % (d, x))


def analyze(a):
    text = open(a.log, errors="replace").read()
    snaps, tl = parse_log(text)
    gpu_iv = swap_iv = []
    if a.dump and os.path.exists(a.dump):
        dtl, gpu_iv, swap_iv = parse_dump(a.dump)
        if dtl and not tl:
            tl = dtl
    if not snaps:
        print("no `codmod ap:` line found in %s (was r_frameWarp 2 running? log filtered too hard?)" % a.log)
        return 2
    final = snaps[-1]["kv"]
    start = None
    for s in snaps:
        if s["tag"] == "start":
            start = s
            break
    # apstats counters downs/ups/misses/probes are controller totals (not cleared by `apstats reset`): use deltas from "start"
    def delta(key):
        v = final.get(key, 0)
        if start is not None and key in start["kv"]:
            v = v - start["kv"][key]
        return v

    print("== apstats (final snapshot) ==")
    keys = ["running", "k", "slot", "real_fps", "frames", "span_s", "distinct_per_s", "gpuclk_distinct_per_s", "distinct_iv_p98", "ll_est_fps", "iv_p2",
            "iv_p50", "iv_p98", "iv_gt1p5T%", "s2g_p50", "s2g_p98", "swap_p98", "wcost_p50", "wcost_p98", "gap_p98",
            "fe_p50", "fe_p98", "hold_mean", "sleeps", "misses", "busy_us_per_real", "denies_slower_ll", "denies_gpu_hold", "deny"]
    print("  " + "  ".join("%s=%s" % (k, final[k]) for k in keys if k in final))
    span = final.get("span_s") or 0
    print("== controller (deltas since the post-warmup snapshot) ==")
    downs, ups, probes, misses = delta("downs"), delta("ups"), delta("probes"), delta("misses")
    trials = None
    if "head" in snaps[-1] and snaps[-1]["head"]:
        h = snaps[-1]["head"]
        print("  head line: " + "  ".join("%s=%s" % kv for kv in h.items()))
        if start is not None and start["head"]:
            for k in ("downs", "kept", "probes", "misses", "reverts"):
                if k in h and k in start["head"]:
                    print("  delta %s = %d" % (k, h[k] - start["head"][k]))
    print("  downs=%s ups=%s probes=%s misses=%s reverts=%s" % (downs, ups, probes, misses, delta("reverts")))
    # head-line downs / kept (ups) are the same counters; take them for pass/fail
    if snaps[-1]["head"] and start is not None and start["head"] and "downs" in snaps[-1]["head"]:
        h, h0 = snaps[-1]["head"], start["head"]
        downs = h.get("downs", 0) - h0.get("downs", 0)
        ups = h.get("kept", 0) - h0.get("kept", 0)
        probes = h.get("probes", 0) - h0.get("probes", 0)
    print("== per-phase snapshots ==")
    prev = start["kv"] if start else None
    for s in snaps:
        if s["tag"] and s["tag"].startswith("end "):
            kv = s["kv"]
            print("  %-10s real_fps=%-6s busy_us_per_real=%-6s slot=%-6s iv_p2/50/98=%s/%s/%s distinct/s=%s misses=%s sleeps=%s" % (
                s["tag"], kv.get("real_fps"), kv.get("busy_us_per_real"), kv.get("slot"), kv.get("iv_p2"), kv.get("iv_p50"),
                kv.get("iv_p98"), kv.get("distinct_per_s"), kv.get("misses"), kv.get("sleeps")))
    print("   (snapshots are cumulative since `apstats reset`: busy_us_per_real is the running mean, not the phase mean)")

    print("== present intervals ==")
    p2, p50, p98 = final.get("iv_p2"), final.get("iv_p50"), final.get("iv_p98")
    print("  apstats: p2=%s p50=%s p98=%s us" % (p2, p50, p98))
    if p2 is not None and p98 is not None:
        print("  interval std approx (P98-P2)/4.1 = %.0f us (apstats has no std)" % ((p98 - p2) / 4.1))
    for name, iv in (("GPU-completion", gpu_iv), ("swap-return", swap_iv)):
        iv = [x for x in iv if x < 100000]
        if iv:
            print("  dump %s n=%d mean=%.0f std=%.0f P1=%.0f P50=%.0f P99=%.0f us" % (
                name, len(iv), statistics.mean(iv), statistics.pstdev(iv), pct(iv, 1), pct(iv, 50), pct(iv, 99)))
    if not gpu_iv:
        print("  (no `apstats dump` file given or found: pass --dump run/home/codmod/apdump.txt for std, P1/P99)")

    verdict = []
    print("== thresholds ==")
    n100 = max(span, 1e-9) / 100.0
    # use the scenario's wall span when the timeline gives it
    if tl:
        wall = tl[-1]["t"] - tl[0]["t"] + 0.25
        n100 = max(wall, 1e-9) / 100.0
        print("  timeline: %d buckets, %.1f s" % (len(tl), wall))
    changes = downs + ups
    rate = changes / n100
    ok = rate <= THRESH["changes_per_100s"]
    print("  downs+ups = %d over %.1f s -> %.2f per 100 s (limit %.1f): %s" % (changes, n100 * 100, rate, THRESH["changes_per_100s"], "PASS" if ok else "FAIL"))
    verdict.append(ok)
    if tl and len(tl) > 6:
        d = [b["dist"] * 4 for b in tl[1:-1]]
        med = statistics.median(d)
        p5 = pct(d, 5)
        ok = p5 >= THRESH["p5_vs_median"] * med
        print("  250 ms-bucket distinct/s (swap-return clock): median=%.0f P5=%.0f ratio=%.3f (need >= %.2f): %s" % (med, p5, p5 / med if med else 0, THRESH["p5_vs_median"], "PASS" if ok else "FAIL"))
        verdict.append(ok)
        # busy by load phase using the bucket mean busy (us per real frame): shows whether the load wave reached the GPU
        b = [x["busy"] for x in tl if x["busy"] > 0]
        if b:
            print("  timeline busy_mean per bucket: P5=%.0f P50=%.0f P95=%.0f max=%.0f us" % (pct(b, 5), pct(b, 50), pct(b, 95), max(b)))
    else:
        print("  250 ms-bucket distinct/s: not evaluated (no `apstats timeline` / dump rows in the log)")

    cur = {"misses": delta("misses") if "misses" in final else None, "sleeps": final.get("sleeps"), "span_s": span}
    if a.baseline and os.path.exists(a.baseline):
        base = json.load(open(a.baseline))
        for k in ("misses", "sleeps"):
            if cur.get(k) is None or base.get(k) is None:
                continue
            # per second of AP time so runs of different span compare
            c = cur[k] / max(cur["span_s"], 1e-9)
            b = base[k] / max(base.get("span_s") or cur["span_s"], 1e-9)
            ok = c <= b * 1.05 + 1e-9
            print("  %s: %s (%.3f/s) vs baseline %s (%.3f/s): %s" % (k, cur[k], c, base[k], b, "PASS" if ok else "FAIL"))
            verdict.append(ok)
    elif a.baseline:
        print("  baseline file %s not found: misses/sleeps not compared (use --save-baseline)" % a.baseline)
    if a.save_baseline:
        json.dump({"misses": cur["misses"], "sleeps": cur["sleeps"], "span_s": cur["span_s"], "downs": downs, "ups": ups,
                   "saved": time.strftime("%Y-%m-%d")}, open(a.save_baseline, "w"), indent=1)
        print("  baseline saved to %s" % a.save_baseline)

    if a.smi:
        smi_summary(a.smi)
    print("== RESULT: %s ==" % ("PASS" if all(verdict) else "FAIL"))
    return 0 if all(verdict) else 1


# ------------------------------------------------------------------ nvidia-smi

SMI_QUERY = "clocks.gr,pstate,power.draw,utilization.gpu"


def cmd_smi(a):
    if a.summarize:
        smi_summary(a.summarize)
        return 0
    if not shutil.which("nvidia-smi"):
        print("nvidia-smi not found: GPU clock logging skipped")
        return 0
    cmd = ["nvidia-smi", "--query-gpu=" + SMI_QUERY, "--format=csv,nounits", "-lms", str(a.interval)]
    print("logging to %s for %d s (Ctrl+C to stop early)" % (a.out, a.seconds))
    t0 = time.time()
    with open(a.out, "w") as f:
        f.write("# start_epoch %.3f interval_ms %d\n" % (t0, a.interval))
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.DEVNULL)
        try:
            while time.time() - t0 < a.seconds and p.poll() is None:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
    smi_summary(a.out)
    return 0


def smi_summary(path):
    rows, interval = [], 100
    for line in open(path, errors="replace"):
        if line.startswith("# start_epoch"):
            m = re.search(r"interval_ms (\d+)", line)
            interval = int(m.group(1)) if m else interval
            continue
        p = [x.strip() for x in line.split(",")]
        if len(p) < 4 or not re.match(r"^\d+", p[0]):
            continue
        try:
            rows.append((int(p[0]), p[1], float(p[2]), float(p[3])))
        except ValueError:
            pass
    print("== GPU clocks (%s, %d samples, ~%d ms apart) ==" % (path, len(rows), interval))
    if not rows:
        print("  no samples")
        return
    clk = [r[0] for r in rows]
    mx = max(clk)
    hi = [c for c in clk if c >= 0.9 * mx]
    print("  clocks.gr MHz: min=%d P5=%d P50=%d max=%d; power %.0f W mean; util %.0f%% mean" % (
        min(clk), pct(clk, 5), pct(clk, 50), mx, statistics.mean(r[2] for r in rows), statistics.mean(r[3] for r in rows)))
    low = sum(1 for c in clk if c < 0.9 * mx)
    print("  samples below 90%% of max clock: %d (%.1f%%); pstates: %s" % (low, 100.0 * low / len(clk), ", ".join(sorted(set(r[1] for r in rows)))))
    # clock vs time: 5 s bins
    n = max(1, int(5000 / interval))
    print("  clock vs time (5 s bins, min/mean MHz):")
    line = []
    for i in range(0, len(rows), n):
        b = clk[i:i + n]
        line.append("%ds:%d/%d" % (i * interval / 1000, min(b), statistics.mean(b)))
    for i in range(0, len(line), 8):
        print("    " + "  ".join(line[i:i + 8]))
    # count drop events: transitions from >=90% max to <80% max
    drops, state = 0, True
    for c in clk:
        if state and c < 0.8 * mx:
            drops += 1
            state = False
        elif not state and c >= 0.9 * mx:
            state = True
    print("  clock drop events (>=0.9 max to <0.8 max): %d" % drops)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("args", help="print console_log arguments")
    p.add_argument("--duration", type=int, default=100, help="seconds of square wave (default 100)")
    p.add_argument("--period", type=int, default=10, help="seconds per phase (default 10)")
    p.add_argument("--hz", type=int, default=233)
    p.set_defaults(fn=cmd_args)
    p = sub.add_parser("analyze", help="analyze a saved console log")
    p.add_argument("log")
    p.add_argument("--dump", help="apdump.txt written by `apstats dump` (run/home/codmod/apdump.txt)")
    p.add_argument("--baseline", help="JSON baseline (misses, sleeps) to compare against")
    p.add_argument("--save-baseline", help="write this run as the baseline")
    p.add_argument("--smi", help="nvidia-smi CSV from the `smi` subcommand")
    p.set_defaults(fn=lambda a: analyze(a))
    p = sub.add_parser("smi", help="log nvidia-smi clocks (background) or summarise a CSV")
    p.add_argument("--out", default="/tmp/ap-smi.csv")
    p.add_argument("--seconds", type=int, default=180)
    p.add_argument("--interval", type=int, default=100)
    p.add_argument("--summarize", help="only summarise this CSV")
    p.set_defaults(fn=cmd_smi)
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
