#!/usr/bin/env bash
# Interleaved A/B profile of two conditions (cvars) on the bench demo, headless: warm-up leg, then A B B A A B B A ...
# Interleaving spreads thermal / clock drift over both conditions. Each leg is one mode-1 profile run (single bench
# run, no warm-up inside), stored under profiling/<stamp>-ab-<label>/{A,B}/mode1/runK (A's run1 = warm-up leg, excluded by
# profile-compare.py; B starts at run2). Compare with: scripts/profile-compare.py <dir>/A <dir>/B
# --profile 0 runs the legs with the profiler off (bench.sh without --profile): each leg keeps only bench_line.txt and
# bench_frametimes.txt (no frames.csv, so profile-compare.py needs the fps-only fallback before it can compare them).
# Usage: scripts/profile-ab.sh --label NAME [--legs N] [--profile 0|1|2] --a "r_foo 0" --b "r_foo 1" [-- common bench.sh args]
#   --a / --b: space-separated "CVAR VALUE [CVAR VALUE ...]" applied to that condition (empty string = defaults)
#   --legs N : measured legs per condition (default 4); total runs = 1 warm-up + 2N
#   --profile N : 1 (default) = full profiler per leg, 0 = profiler off, 2 = also per-shader batch timings (slow)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOME_CFG="$ROOT/run/home/codmod"
LABEL="ab"; LEGS=4; PROFILE=1; A=""; B=""; COMMON=()
while [[ $# -gt 0 ]]; do
	case "$1" in
		--label) LABEL="$2"; shift 2 ;;
		--legs) LEGS="$2"; shift 2 ;;
		--profile) PROFILE="$2"; shift 2 ;;
		--a) A="$2"; shift 2 ;;
		--b) B="$2"; shift 2 ;;
		--) shift; COMMON=("$@"); break ;;
		*) echo "unknown arg: $1" >&2; exit 1 ;;
	esac
done
case "$PROFILE" in
	0|1|2) ;;
	*) echo "--profile must be 0, 1 or 2 (got: $PROFILE)" >&2; exit 1 ;;
esac
DIR="$ROOT/profiling/$(date +%Y%m%d-%H%M%S)-ab-$LABEL"
mkdir -p "$DIR/A/mode1" "$DIR/B/mode1"
"$ROOT/scripts/profile-env.sh" "$DIR/environment" >/dev/null
printf 'A: %s\nB: %s\ncommon: %s\nlegs per condition: %s (plus 1 warm-up leg of A)\nprofile: %s (0 = profiler off)\n' \
	"$A" "$B" "${COMMON[*]:-}" "$LEGS" "$PROFILE" > "$DIR/conditions.txt"

# ABBA ordering: A B B A A B B A ...; the warm-up leg is an extra A run named run1 of A
ORDER=()
for ((i = 0; i < LEGS; i++)); do
	if ((i % 2 == 0)); then ORDER+=(A B); else ORDER+=(B A); fi
done
declare -A COUNT=([A]=1 [B]=1)

leg() { # condition, run index
	local cond="$1" idx="$2" spec="$A" args=()
	[[ "$cond" == B ]] && spec="$B"
	read -r -a toks <<< "$spec"
	for ((k = 0; k + 1 < ${#toks[@]}; k += 2)); do args+=(--set "${toks[k]}" "${toks[k+1]}"); done
	if ((PROFILE)); then
		local tmp="$DIR/.leg"
		PROFILE_OUT="$tmp" "$ROOT/scripts/bench.sh" --label "ab-$LABEL-$cond" --runs 1 --profile "$PROFILE" "${COMMON[@]}" "${args[@]}" | tail -n 3
		mv "$tmp/run1" "$DIR/$cond/mode1/run$idx"
		rmdir "$tmp" 2>/dev/null || true
	else
		# no --profile: bench.sh writes no profiling/ files; keep the frame-time log and the "codmod bench:" result line
		# from the console log (bench.sh truncates that log at the start of each run, so it still holds this leg)
		"$ROOT/scripts/bench.sh" --label "ab-$LABEL-$cond" --runs 1 "${COMMON[@]}" "${args[@]}" | tail -n 3
		local dst="$DIR/$cond/mode1/run$idx"
		mkdir -p "$dst"
		cp -f "$HOME_CFG/benchmarks/last_frametimes.txt" "$dst/bench_frametimes.txt" \
			|| echo "WARNING: no last_frametimes.txt for $cond run$idx" >&2
		grep -a 'codmod bench: frames=' "$HOME_CFG/rtcwconsole.log" | tail -n 1 | sed 's/.*codmod bench: //' > "$dst/bench_line.txt"
	fi
}

echo ">> warm-up leg (A, discarded)"
leg A 1
for c in "${ORDER[@]}"; do
	COUNT[$c]=$((COUNT[$c] + 1))
	echo ">> leg $c run${COUNT[$c]}"
	leg "$c" "${COUNT[$c]}"
done
echo "interleaved A/B written to $DIR"
echo "compare: scripts/profile-compare.py $DIR/A $DIR/B"
