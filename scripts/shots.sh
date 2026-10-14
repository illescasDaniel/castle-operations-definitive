#!/usr/bin/env bash
# Deterministic screenshots of the benchmark demo, for checking that a renderer change does not
# alter the image. timedemo steps the demo 50 ms of game time per frame, so frame N is the same
# moment on every run; a screenshot is taken every STEP frames. Compare two labels with
# scripts/shots-diff.py. wolfconfig.cfg is restored afterwards (same as bench.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOME_CFG="$ROOT/run/home/codmod"
LABEL="shots"
COUNT=6
STEP=70
SET_ARGS=()

usage() {
	cat <<'USAGE'
Usage: scripts/shots.sh [--label NAME] [--count N] [--step FRAMES] [--set CVAR VALUE]...

  Saves benchmarks/shots/NAME/shotNN.tga (default 6 shots, every 70 demo frames = 3.5 s)
USAGE
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--label) LABEL="$2"; shift 2 ;;
		--count) COUNT="$2"; shift 2 ;;
		--step) STEP="$2"; shift 2 ;;
		--set) SET_ARGS+=("$2=$3"); shift 3 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "unknown arg: $1" >&2; usage >&2; exit 1 ;;
	esac
done

CFG="$HOME_CFG/wolfconfig.cfg"
SAVED="$(mktemp)"
[[ -f "$CFG" ]] && cp -f "$CFG" "$SAVED" || : > "$SAVED"
restore() {
	[[ -s "$SAVED" ]] && cp -f "$SAVED" "$CFG"
	rm -f "$SAVED" "$HOME_CFG/shots_pre.cfg" "$HOME_CFG/shots_post.cfg"
}
trap restore EXIT

OUT="$ROOT/benchmarks/shots/$LABEL"
rm -rf "$OUT" "$HOME_CFG/screenshots/codmod_shot"*
mkdir -p "$OUT"

{
	printf 'set com_maxfps 0\nset timedemo 1\nset nextdemo quit\n'
	for kv in "${SET_ARGS[@]}"; do echo "seta ${kv%%=*} \"${kv#*=}\""; done
} > "$HOME_CFG/shots_pre.cfg"
# "wait N" defers the rest of the buffer by N frames (one demo step each under timedemo);
# a separate cfg after "demo" so the waits do not delay the demo start
line=""
for ((i = 1; i <= COUNT; i++)); do
	line+="wait $STEP; screenshot codmod_shot$(printf '%02d' "$i"); "
done
echo "$line" > "$HOME_CFG/shots_post.cfg"

RTCW_STARTUP_SETS="${SET_ARGS[*]}" "$ROOT/scripts/run.sh" +exec shots_pre.cfg +demo codmod_bench +exec shots_post.cfg >/dev/null 2>&1 || true

n=0
for f in "$HOME_CFG"/screenshots/codmod_shot*.tga; do
	[[ -f "$f" ]] || continue
	mv -f "$f" "$OUT/$(basename "$f" | sed 's/codmod_//')"
	n=$((n + 1))
done
echo "saved $n screenshot(s) to $OUT"
