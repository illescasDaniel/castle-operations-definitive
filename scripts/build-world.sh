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
if command -v julia >/dev/null; then
	RUN=(julia -O2 --project="$ROOT/tools/world-bevel-jl" "$ROOT/tools/world-bevel-jl/world_bevel.jl")
else
	echo "julia not found: using the Python tool (about 80-110 s per map instead of ~8 s; see tools/world-bevel-jl/README.md)" >&2
	RUN=(python3 -I "$ROOT/tools/world-bevel/world_bevel.py")
fi
fail=()
for m in "${maps[@]}"; do
	echo "== $m"
	tmp="$OUT/codmod_bevel_$m.pk3.tmp"
	if "${RUN[@]}" --map "$m" --uv-mode align --min-angle 15 --smooth-models --stats --pk3 "$tmp" >"$ROOT/benchmarks/world-$m.log" 2>&1; then
		mv -f "$tmp" "$OUT/codmod_bevel_$m.pk3"
	else
		echo "   FAILED (see benchmarks/world-$m.log)"
		fail+=("$m")
		[[ -f "$tmp" ]] && trash "$tmp"
	fi
done
echo "failed: ${fail[*]:-none}"
