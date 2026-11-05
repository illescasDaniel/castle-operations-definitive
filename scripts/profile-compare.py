#!/usr/bin/env python3
"""Compare two scripts/profile.sh sessions (or profile-ab.sh legs): per-run values, median and range of FPS, 1% low, GPU frame
time (mean, P95, P99) and the biggest per-pass differences, over the bench window of the measured mode 1 runs (run1 = warm-up,
skipped). Percentiles are computed per run from that run's own frames (never pooled); the report is the median [min-max]
across runs. Percentile = nearest-lower rank: sorted[floor(q * (n - 1))], no interpolation.

Usage: scripts/profile-compare.py A_DIR B_DIR [--window START_MS-END_MS ...] [--cols NAME,NAME,...]
  --window   keep frames with START_MS <= ref_time_ms < END_MS (game time, frames.csv), applied after the bench-window
             filter. Repeatable: stats are over the union of the windows. FPS and 1% low come from bench_line.txt and always
             cover the whole bench.
  --cols     median [min-max] of these frames.csv columns (e.g. cpu_mds_tangent_depth_ms,cnt_mds_tangent_verts_depth,
             pass_sunshadow_ms): per run the mean over the selected rows, then median across runs.
  A run without frames.csv (profiler-off legs) reports FPS and 1% low only.
e.g. scripts/profile-compare.py profiling/latest profiling/20261105-103545-framewarp-off"""
import argparse, csv, math, re, statistics, sys
from pathlib import Path

WINDOW_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*$")


def runs(d):
    m = Path(d) / "mode1"
    rs = sorted((x for x in m.glob("run*") if x.is_dir()), key=lambda x: int(x.name[3:]))
    return [x for x in rs if x.name != "run1"] or rs


def fl(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def bench_kv(rd):
    """key=value summary of a run: bench_line.txt, else the '# frames=' header of bench_frametimes.txt"""
    p = rd / "bench_line.txt"
    if p.is_file():
        text = p.read_text()
    else:
        p = rd / "bench_frametimes.txt"
        text = next((t for t in p.read_text().splitlines() if t.startswith("# frames=")), "") if p.is_file() else ""
    return {k: fl(v) for k, v in (t.split("=", 1) for t in text.split() if "=" in t)}


def load(rd, windows):
    """frames of a run (bench window, then --window union), or None when frames.csv is absent"""
    p = rd / "frames.csv"
    if not p.is_file():
        return None
    with p.open() as f:
        rows = list(csv.DictReader(f))
    if rows and "bench_window" in rows[0]:
        rows = [r for r in rows if r["bench_window"] == "1"]
    else:
        rows = [r for r in rows if int(r["frame"]) >= 60]
    if windows and rows:
        if "ref_time_ms" not in rows[0]:
            sys.exit(f"{p}: no ref_time_ms column, --window cannot be applied")
        rows = [r for r in rows if any(lo <= fl(r["ref_time_ms"], -1.0) < hi for lo, hi in windows)]
    return rows


def pctl(v, q):
    """nearest-lower rank: sorted[floor(q * (n - 1))]"""
    s = sorted(v)
    return s[math.floor(q * (len(s) - 1))] if s else None


def summarize(d, windows, cols):
    out = {"fps": [], "low1": [], "gpu": [], "p95": [], "p99": [], "frames": [], "pass": {}, "no_frames": [],
           "cols": {c: [] for c in cols}, "seen": set()}
    for rd in runs(d):
        kv = bench_kv(rd)
        if kv.get("avg_fps") is not None:
            out["fps"].append(kv["avg_fps"])
        if kv.get("low1_fps") is not None:
            out["low1"].append(kv["low1_fps"])
        rows = load(rd, windows)
        if rows is None:
            out["no_frames"].append(rd.name)
            continue
        out["frames"].append(len(rows))
        if not rows:
            continue
        g = [fl(r["gpu_ms"], 0.0) for r in rows]
        out["gpu"].append(statistics.fmean(g))
        out["p95"].append(pctl(g, 0.95))
        out["p99"].append(pctl(g, 0.99))
        for c in rows[0]:
            if c.startswith("pass_") and c.endswith("_ms"):
                out["pass"].setdefault(c[5:-3], []).append(statistics.fmean(fl(r[c], 0.0) for r in rows))
        for c in cols:
            if c in rows[0]:
                out["seen"].add(c)
                out["cols"][c].append(statistics.fmean(fl(r[c], 0.0) for r in rows))
    return out


def fmt(v, f="{:.3f}"):
    if not v:
        return "-"
    return f"{f.format(statistics.median(v))} [{f.format(min(v))}-{f.format(max(v))}] n={len(v)}"


def pair(label, a, b, f):
    print(f"{label:<12}A {fmt(a, f)}\n{'':<12}B {fmt(b, f)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a_dir", metavar="A_DIR")
    ap.add_argument("b_dir", metavar="B_DIR")
    ap.add_argument("--window", action="append", default=[], metavar="START_MS-END_MS",
                    help="frames with START_MS <= ref_time_ms < END_MS; repeatable (union)")
    ap.add_argument("--cols", default="", metavar="NAME,NAME",
                    help="frames.csv columns to report as median [range] of per-run means (e.g. cpu_*, cnt_*, pass_*)")
    args = ap.parse_args()
    windows = []
    for w in args.window:
        m = WINDOW_RE.match(w)
        if not m or float(m.group(1)) >= float(m.group(2)):
            ap.error(f"--window expects START_MS-END_MS with START < END, got {w!r}")
        windows.append((float(m.group(1)), float(m.group(2))))
    cols = [c.strip() for c in args.cols.split(",") if c.strip()]
    a, b = summarize(args.a_dir, windows, cols), summarize(args.b_dir, windows, cols)

    print(f"A = {args.a_dir}\nB = {args.b_dir}")
    if windows:
        print("window(s) on ref_time_ms, start <= t < end, union: " + ", ".join(f"[{lo:g}, {hi:g})" for lo, hi in windows))
        print("fps and 1% low are whole-bench values (bench_line.txt); gpu, frames and --cols use the window rows only")
    for side, s in (("A", a), ("B", b)):
        if s["no_frames"]:
            print(f"{side}: no frames.csv in {', '.join(s['no_frames'])}: FPS and 1% low only for these runs")
    print()
    pair("fps", a["fps"], b["fps"], "{:.2f}")
    pair("1% low fps", a["low1"], b["low1"], "{:.2f}")
    pair("gpu ms", a["gpu"], b["gpu"], "{:.4f}")
    pair("gpu p95 ms", a["p95"], b["p95"], "{:.4f}")
    pair("gpu p99 ms", a["p99"], b["p99"], "{:.4f}")
    pair("frames", a["frames"], b["frames"], "{:.0f}")
    if a["gpu"] and b["gpu"]:
        ma, mb = statistics.median(a["gpu"]), statistics.median(b["gpu"])
        overlap = max(min(a["gpu"]), min(b["gpu"])) <= min(max(a["gpu"]), max(b["gpu"]))
        print(f"{'gpu delta':<12}B vs A {100 * (mb - ma) / ma:+.1f}% ({'ranges OVERLAP: inconclusive' if overlap else 'ranges separate'})")
    if cols:
        print("\n--cols: per-run mean over the selected rows, median [min-max] across runs:")
        for c in cols:
            print(f"  {c}")
            print(f"    A {fmt(a['cols'][c], '{:.4f}')}\n    B {fmt(b['cols'][c], '{:.4f}')}")
        absent = [c for c in cols if c not in a["seen"] | b["seen"]]
        if absent:
            print(f"  not in any frames.csv: {', '.join(absent)}")
    print("\nper-pass median ms/frame, biggest absolute differences:")
    names = set(a["pass"]) | set(b["pass"])
    rows = []
    for n in names:
        ma = statistics.median(a["pass"].get(n, [0.0]))
        mb = statistics.median(b["pass"].get(n, [0.0]))
        rows.append((abs(mb - ma), n, ma, mb))
    for _, n, ma, mb in sorted(rows, reverse=True)[:15]:
        print(f"  {n:28s} A {ma:.4f}  B {mb:.4f}  delta {mb - ma:+.4f}")


if __name__ == "__main__":
    main()
