#!/usr/bin/env bash
# Build the private world packs (corner bevel + baked-prop smoothing) for all maps, or the named ones, with the Julia
# port. Output: run/codmod/codmod_bevel_MAP.pk3 (git-ignored, derived from RTCW maps). See tools/world-bevel-jl/README.md.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/run/codmod"
maps=("$@")
if [[ ${#maps[@]} -eq 0 ]]; then
	mapfile -t maps < <(python3 -I -c "
import sys; sys.path.insert(0, '$ROOT/tools/world-bevel')
import world_bevel as w
print('\n'.join(w.all_maps()))")
fi
mkdir -p "$ROOT/benchmarks"
# Julia only: the Python tool lacks the hole fixes (reject_touched_edges!), so it is no longer a fallback.
if ! command -v julia >/dev/null; then
	echo "julia not found (1.10+ required): the Python world_bevel.py leaves white holes, see tools/world-bevel-jl/README.md" >&2
	exit 1
fi
RUN=(julia -O2 --project="$ROOT/tools/world-bevel-jl" "$ROOT/tools/world-bevel-jl/world_bevel.jl")
# Maps are independent single-threaded jobs: run JOBS (default 8) at once; each job writes its own log and tmp pack.
JOBS="${JOBS:-8}"
build_one() {
	local m="$1" tmp="$OUT/codmod_bevel_$1.pk3.tmp"
	if "${RUN[@]}" --map "$m" --uv-mode align --min-angle 15 --smooth-models --stats --pk3 "$tmp" >"$ROOT/benchmarks/world-$m.log" 2>&1; then
		mv -f "$tmp" "$OUT/codmod_bevel_$m.pk3"
		echo "== $m ok"
	else
		echo "== $m FAILED (see benchmarks/world-$m.log)"
		[[ -f "$tmp" ]] && trash "$tmp"
		return 1
	fi
}
FAILDIR="$(mktemp -d)"
running=0
for m in "${maps[@]}"; do
	build_one "$m" || : >"$FAILDIR/$m" &
	running=$((running + 1))
	if ((running >= JOBS)); then
		wait -n || true
		running=$((running - 1))
	fi
done
wait
mapfile -t fail < <(ls "$FAILDIR")
trash "$FAILDIR"
echo "failed: ${fail[*]:-none}"
