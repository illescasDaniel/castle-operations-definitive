#!/usr/bin/env bash
# Full render profile of the bench demo, written to profiling/<stamp>-<label>/ (git-ignored, agent-readable).
#   mode1/  r_gpuProfile 1: honest FPS + GPU pass times + CPU scopes + per-frame rows (run 1 = warm-up, rest measured)
#   mode2/  r_gpuProfile 2: per-shader / per-batch GPU+CPU times (timestamp pairs per draw: slower, FPS not representative)
#   environment/  git SHAs + dirty diffs, binary / demo hashes, pack names, mod cfgs, GPU info (what produced the data)
# Runs headless off-screen through bench.sh. Extra args go to both bench.sh calls (e.g. --set r_frameWarp 0).
# Default protocol: mode 1 = 1 warm-up + 3 measured runs (report gives per-run values, median and range), mode 2 = 1 + 1.
# Opt-in --mem: a third pass (mem/, 1 warm-up + 1 measured, r_gpuProfile off, com_memProfile 1) for the RAM+VRAM memory
# profiler (docs/memory-profiler-plan.md); the report adds a Memory section and mem_categories.csv / mem_timeline.csv.
# Usage: scripts/profile.sh [--label NAME] [--runs N] [--runs2 N] [--mem] [bench.sh args...]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="profile"
RUNS=4
RUNS2=2
MEM=0
ARGS=()
while [[ $# -gt 0 ]]; do
	case "$1" in
		--label) LABEL="$2"; shift 2 ;;
		--runs) RUNS="$2"; shift 2 ;;
		--runs2) RUNS2="$2"; shift 2 ;;
		--mem) MEM=1; shift ;;
		*) ARGS+=("$1"); shift ;;
	esac
done
STAMP="$(date +%Y%m%d-%H%M%S)"
DIR="$ROOT/profiling/$STAMP-$LABEL"
mkdir -p "$DIR"
"$ROOT/scripts/profile-env.sh" "$DIR/environment"
for mode in 1 2; do
	n="$RUNS"; [[ $mode == 2 ]] && n="$RUNS2"
	PROFILE_OUT="$DIR/mode$mode" "$ROOT/scripts/bench.sh" --label "$LABEL-mode$mode" --runs "$n" --profile "$mode" "${ARGS[@]}" \
		| tee "$DIR/bench-mode$mode.log"
done
if ((MEM)); then
	# separate pass: the gpuprof arrays inflate RSS and the periodic memory samples add hitches, so it never shares a run
	PROFILE_OUT="$DIR/mem" "$ROOT/scripts/bench.sh" --label "$LABEL-mem" --runs 2 --memprof "${ARGS[@]}" \
		| tee "$DIR/bench-mem.log"
fi
python3 "$ROOT/scripts/profile-report.py" "$DIR" --label "$LABEL" --args "${ARGS[*]:-}"
ln -sfn "$(basename "$DIR")" "$ROOT/profiling/latest"
echo "profile written to $DIR (profiling/latest); start with profiling/latest/summary.md"
