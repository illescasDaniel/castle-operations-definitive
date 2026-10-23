#!/usr/bin/env bash
# Load-timing harness: loads each map off-screen in a headless gamescope with the engine's load profiler
# (com_loadProfile) and checks that no present-to-present gap during the load exceeds 33 ms.
# Parses "LOADPROFILE ..." / "LOADPROFILE_GAP ..." lines from the console log. wolfconfig.cfg is restored.
# Usage: scripts/load-test.sh [--maps "escape1 escape2 village1"] [--level-change] [--profile-level N]
#   --level-change   after the first load, also change level (map escape2, or escape1 if that is the first map)
#                    and profile that load too
#   --profile-level  com_loadProfile value (default 1; 2 adds LOADPROFILE_MARK stage lines)
# Exit code: 0 if every load has over33 == 0, 1 on any FAIL / missing result / hung run.
# Raw logs are kept in benchmarks/load-<stamp>-<map>.log (not committed).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
H="$ROOT/run/home/codmod"
LOG="$H/rtcwconsole.log"
OUT="$ROOT/benchmarks"
MAPS="escape1 escape2 village1"
LEVEL_CHANGE=0
PLEVEL=1
while [[ $# -gt 0 ]]; do
	case "$1" in
		--maps) MAPS="$2"; shift 2 ;;
		--level-change) LEVEL_CHANGE=1; shift ;;
		--profile-level) PLEVEL="$2"; shift 2 ;;
		-h|--help) sed -n '2,10p' "$0"; exit 0 ;;
		*) echo "unknown arg: $1" >&2; exit 1 ;;
	esac
done

mkdir -p "$OUT"
CFG="$H/wolfconfig.cfg"; SAVED="$(mktemp)"
[[ -f "$CFG" ]] && cp -f "$CFG" "$SAVED"
trap '[[ -s "$SAVED" ]] && cp -f "$SAVED" "$CFG"; trash "$SAVED" "$H/loadtest.cfg" 2>/dev/null || true' EXIT

STAMP="$(date +%Y%m%d-%H%M%S)"
overall=0

for map in $MAPS; do
	# Waits count frames (not ms). Quit only after a generous wait: a scripted quit during map load segfaults.
	cfg="wait 600; uiclick 612 466; wait 5; uiclick; wait 600;"
	second=""
	if ((LEVEL_CHANGE)); then
		second=escape2; [[ "$map" == escape2 ]] && second=escape1
		cfg+=" map $second; wait 600; uiclick 612 466; wait 5; uiclick; wait 600;"
	fi
	echo "$cfg wait 5; quit" > "$H/loadtest.cfg"

	echo ">> $map${second:+ (+ level change to $second)}"
	: > "$LOG"
	rc=0
	(timeout 300 gamescope --backend headless -W 1920 -H 1200 -- "$ROOT/scripts/run.sh" --windowed 1920x1200 \
		+set com_loadProfile "$PLEVEL" +spdevmap "$map" +exec loadtest.cfg >/dev/null 2>&1) || rc=$?
	RAW="$OUT/load-$STAMP-$map.log"
	cp -f "$LOG" "$RAW" 2>/dev/null || : > "$RAW"
	if ((rc == 124)); then
		echo "   HUNG: timeout fired after 300 s (log: $RAW)"; overall=1
	fi

	python3 - "$RAW" "$map" <<'PY' || overall=1
import re, sys
log, name = sys.argv[1], sys.argv[2]
sum_re = re.compile(r"LOADPROFILE (\S+) total=([\d.]+)ms frames=(\d+) maxgap=([\d.]+)ms@(\S+) p95=([\d.]+)ms over33=(\d+)")
gap_re = re.compile(r"LOADPROFILE_GAP ([\d.]+)ms @(\S+) t=([\d.]+)(?: hint=(\S+))?")
loads, gaps, marks = [], [], []
for l in open(log, errors="replace").read().splitlines():
    if (m := sum_re.search(l)):
        loads.append(m.groups()); gaps.append([]); marks.append([])
    elif (m := gap_re.search(l)):
        if not loads:
            continue
        gaps[-1].append(m.groups())
    elif "LOADPROFILE_MARK" in l and loads:
        marks[-1].append(l.split("LOADPROFILE_MARK", 1)[1].strip())
if not loads:
    print(f"   {name}: FAIL, no LOADPROFILE line in the log (load did not finish, or com_loadProfile unsupported)")
    sys.exit(1)
bad = False
print(f"   {'map':10s} {'why':11s} {'total':>8s} {'frames':>7s} {'maxgap@stage':>26s} {'p95':>7s} {'over33':>6s}")
for (why, total, frames, mg, stage, p95, over), g, mk in zip(loads, gaps, marks):
    ok = int(over) == 0
    bad |= not ok
    print(f"   {name:10s} {why:11s} {total+'ms':>8s} {frames:>7s} {mg+'ms@'+stage:>26s} {p95+'ms':>7s} {over:>6s}  {'PASS' if ok else 'FAIL'}")
    for gap, st, t, hint in g:
        print(f"      gap {gap:>7s} ms @ {st}  t={t} ms  hint={hint or '-'}")
    for line in mk:
        print(f"      mark {line}")
sys.exit(1 if bad else 0)
PY
done

echo
if ((overall)); then echo "load-test: FAIL"; else echo "load-test: PASS"; fi
exit "$overall"
