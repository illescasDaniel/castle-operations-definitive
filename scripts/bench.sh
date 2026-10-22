#!/usr/bin/env bash
# Benchmark: replay mod/codmod/demos/codmod_bench at real time and report frame-time stats.
# Uses the user's own resolution/graphics settings; wolfconfig.cfg is restored afterwards.
# Always runs off-screen in a headless gamescope (no window on the desktop, GPU rendering kept).
# BENCH_ONSCREEN=1 opts out (e.g. for --mangohud overlays); BENCH_HEADLESS_W/H set the size (1920x1200).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOME_CFG="$ROOT/run/home/codmod"
LOG="$HOME_CFG/rtcwconsole.log"
OUT="$ROOT/benchmarks"
LABEL="run"
RUNS=3
LAUNCHER="$ROOT/scripts/run.sh"

usage() {
	cat <<'USAGE'
Usage: scripts/bench.sh [--label NAME] [--runs N] [--mangohud] [--windowed WxH]
                        [--set CVAR VALUE]... [--env KEY=VAL]... [--gpumon]

  --label NAME   Tag for results.csv and saved frame-time logs (default: run)
  --runs N       Runs (default 3); run 1 is a warm-up, excluded from the median
  --mangohud     Launch via game_run.sh (MangoHud + gamemode) for a cross-check
  --windowed WxH Pass through to run.sh
  --set C V      Extra "+set C V" (repeatable; wins over codmod.cfg and saved settings)
  --env K=V      Environment variable for the game process (repeatable)
  --gpumon       Sample GPU/memory utilisation with nvidia-smi during each run
USAGE
}

RUN_ARGS=()
SET_ARGS=()
ENV_ARGS=()
SET_DESC=""
GPUMON=0
while [[ $# -gt 0 ]]; do
	case "$1" in
		--label) LABEL="$2"; shift 2 ;;
		--runs) RUNS="$2"; shift 2 ;;
		--mangohud) LAUNCHER="$ROOT/scripts/game_run.sh"; shift ;;
		--windowed) RUN_ARGS+=(--windowed "$2"); shift 2 ;;
		--set) SET_ARGS+=("$2=$3"); SET_DESC+=" $2=$3"; shift 3 ;;
		--env) ENV_ARGS+=("$2"); SET_DESC+=" $2"; shift 2 ;;
		--gpumon) GPUMON=1; shift ;;
		-h|--help) usage; exit 0 ;;
		*) echo "unknown arg: $1" >&2; usage >&2; exit 1 ;;
	esac
done

DEMO="$ROOT/run/codmod/demos/codmod_bench.dm_50"
if [[ ! -f "$DEMO" ]]; then
	echo "ERROR: $DEMO missing; run scripts/install.sh (demo lives in mod/codmod/demos/)" >&2
	exit 1
fi

WRAP=()
if [[ "${BENCH_ONSCREEN:-0}" != 1 ]]; then
	HW="${BENCH_HEADLESS_W:-1920}"; HH="${BENCH_HEADLESS_H:-1200}"
	WRAP=(gamescope --backend headless -W "$HW" -H "$HH" --)
	[[ ${#RUN_ARGS[@]} -gt 0 ]] || RUN_ARGS=(--windowed "${HW}x${HH}")
fi

mkdir -p "$OUT"
CFG="$HOME_CFG/wolfconfig.cfg"
SAVED="$(mktemp)"
[[ -f "$CFG" ]] && cp -f "$CFG" "$SAVED" || : > "$SAVED"
restore() {
	if [[ -s "$SAVED" ]]; then
		cp -f "$SAVED" "$CFG"
	fi
	rm -f "$SAVED"
}
trap 'restore; rm -f "$HOME_CFG/bench_override.cfg"' EXIT

STAMP="$(date +%Y%m%d-%H%M%S)"
SHA_OUTER="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo ?)"
SHA_ENGINE="$(git -C "$ROOT/iortcw" rev-parse --short HEAD 2>/dev/null || echo ?)"
[[ -f "$OUT/results.csv" ]] || echo "date,label,run,sha_outer,sha_engine,frames,seconds,avg_fps,low1_fps,median_ms,p95_ms,p99_ms,max_ms,hitches,cfg" > "$OUT/results.csv"

declare -a AVGS LOWS P99S
for ((i = 1; i <= RUNS; i++)); do
	echo ">> run $i/$RUNS"
	: > "$LOG"
	GPULOG=""
	if ((GPUMON)); then
		GPULOG="$(mktemp)"
		nvidia-smi dmon -s um -d 1 >"$GPULOG" 2>/dev/null &
		MONPID=$!
	fi
	# Overrides: startup +set (replaces run.sh's, needed for latched cvars) plus a late exec that
	# re-applies them after codmod.cfg (its "seta" would otherwise leave a pending latch).
	# The engine drops "+" command-line commands beyond 32 (MAX_CONSOLE_LINES) and run.sh uses ~27,
	# so everything bench-specific goes into this one cfg instead of extra +set arguments.
	printf 'set com_maxfps 0\nset cl_benchDemo 1\nset nextdemo quit\n' > "$HOME_CFG/bench_override.cfg"
	for kv in "${SET_ARGS[@]}"; do echo "seta ${kv%%=*} \"${kv#*=}\"" >> "$HOME_CFG/bench_override.cfg"; done
	env "${ENV_ARGS[@]}" RTCW_STARTUP_SETS="${SET_ARGS[*]}" "${WRAP[@]}" "$LAUNCHER" "${RUN_ARGS[@]}" +exec bench_override.cfg +demo codmod_bench >/dev/null 2>&1 || true
	gpuinfo=""
	if ((GPUMON)); then
		kill "$MONPID" 2>/dev/null || true; wait "$MONPID" 2>/dev/null || true
		# columns: gpu sm mem enc dec jpg ofa fb bar1 ccpm ; keep only busy samples (sm>20)
		gpuinfo="$(awk '!/^#/ && $2>20 {s+=$2; m+=$3; n++} END{if(n) printf "gpu_sm=%.0f%% gpu_mem=%.0f%%", s/n, m/n}' "$GPULOG")"
		rm -f "$GPULOG"
		echo "   $gpuinfo"
	fi
	line="$(grep -a 'codmod bench: frames=' "$LOG" | tail -1 || true)"
	cfgline="$(grep -a 'codmod bench cfg:' "$LOG" | tail -1 | sed 's/.*codmod bench cfg: //' || true)"
	if [[ -z "$line" ]]; then
		echo "ERROR: no 'codmod bench:' result in $LOG (demo failed to play?)" >&2
		exit 1
	fi
	line="${line#*codmod bench: }"
	declare -A kv=()
	for tok in $line; do kv[${tok%%=*}]=${tok#*=}; done
	grep -a 'WARNING vsync' "$LOG" | tail -1 || true
	printf '   frames=%s  %ss  avg %s fps  1%%low %s fps  P99 %s ms  max %s ms  hitches %s\n' \
		"${kv[frames]}" "${kv[seconds]}" "${kv[avg_fps]}" "${kv[low1_fps]}" "${kv[p99_ms]}" "${kv[max_ms]}" "${kv[hitches]}"
	echo "$STAMP,$LABEL,$i,$SHA_OUTER,$SHA_ENGINE,${kv[frames]},${kv[seconds]},${kv[avg_fps]},${kv[low1_fps]},${kv[median_ms]},${kv[p95_ms]},${kv[p99_ms]},${kv[max_ms]},${kv[hitches]},\"$cfgline${SET_DESC:+ |$SET_DESC} $gpuinfo\"" >> "$OUT/results.csv"
	cp -f "$HOME_CFG/benchmarks/last_frametimes.txt" "$OUT/$STAMP-$LABEL-run$i.txt" 2>/dev/null || true
	if ((i > 1 || RUNS == 1)); then
		AVGS+=("${kv[avg_fps]}"); LOWS+=("${kv[low1_fps]}"); P99S+=("${kv[p99_ms]}")
	fi
done

median() { printf '%s\n' "$@" | sort -g | awk '{a[NR]=$1} END{print (NR%2)?a[(NR+1)/2]:(a[NR/2]+a[NR/2+1])/2}'; }
echo
echo "== $LABEL (median of $((${#AVGS[@]})) measured run(s); engine $SHA_ENGINE, repo $SHA_OUTER)"
echo "   avg $(median "${AVGS[@]}") fps | 1% low $(median "${LOWS[@]}") fps | P99 $(median "${P99S[@]}") ms"
echo "   cfg: $cfgline"
echo "   saved: $OUT/results.csv, $OUT/$STAMP-$LABEL-run*.txt"
