#!/usr/bin/env bash
# Smoke test: view-motion cost. Compares GPU frame time for a still view against fast turns
# (cl_yawspeed 5/100/700) on escape1, off-screen in a headless gamescope. Regression guard for the
# VAO-cache re-upload bug (turning used to cost 2-4x the still-view GPU time). wolfconfig.cfg is restored.
# Usage: scripts/spin-test.sh [--max-ratio R]   (default 1.25: fail if turning GPU time > R x still)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
H="$ROOT/run/home/codmod"
LOG="$H/rtcwconsole.log"
RATIO=1.25
[[ "${1:-}" == --max-ratio ]] && RATIO="$2"
POS="1808.0 1600.0 -759.9"   # escape1, after the intro cutscene: wide view with lots of world geometry

CFG="$H/wolfconfig.cfg"; SAVED="$(mktemp)"
[[ -f "$CFG" ]] && cp -f "$CFG" "$SAVED"
trap '[[ -s "$SAVED" ]] && cp -f "$SAVED" "$CFG"; trash "$SAVED" "$H/spin.cfg" 2>/dev/null || true' EXIT

# Waits count frames: keep the user's frame cap during startup, lift it only afterwards.
cfg="wait 500; uiclick 612 466; wait 5; uiclick; wait 60; god; notarget; cmd cameraInterrupt; wait 100; set com_maxfps 0; set r_gpuProfile 1; wait 100;"
cfg+=" setviewpos $POS 0 0; wait 60; gpuprof reset; wait 100; echo STILL; gpuprof;"
for s in 5 100 700; do
	cfg+=" set cl_yawspeed $s; setviewpos $POS 0 0; wait 40; gpuprof reset; +left; wait 200; -left; echo YAW_$s; gpuprof;"
done
echo "$cfg wait 5; quit" > "$H/spin.cfg"

(timeout 300 gamescope --backend headless -W 1920 -H 1200 -- "$ROOT/scripts/run.sh" --windowed 1920x1200 \
	+spdevmap escape1 +exec spin.cfg >/dev/null 2>&1 || true)

python3 - "$LOG" "$RATIO" <<'PY'
import re, sys
log, ratio = sys.argv[1], float(sys.argv[2])
res, label = {}, None
for l in open(log, errors="replace").read().splitlines():
    if re.match(r"^(STILL|YAW_\d+)$", l):
        label = l
    elif label:
        m = re.search(r"gpuprof: frames=\d+ gpu_avg_ms=([\d.]+)", l)
        if m:
            res[label] = float(m.group(1)); label = None
if "STILL" not in res:
    sys.exit("spin-test: no STILL result in the log (run failed, or the gpuprof output changed)")
base, bad = res["STILL"], False
for k, v in res.items():
    flag = "  <-- FAIL" if k != "STILL" and v > ratio * base else ""
    bad |= bool(flag)
    print(f"{k:9s} GPU {v:6.2f} ms  x{v / base:4.2f}{flag}")
sys.exit(1 if bad else 0)
PY
