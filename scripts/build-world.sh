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
fail=()
for m in "${maps[@]}"; do
	echo "== $m"
	tmp="$OUT/codmod_bevel_$m.pk3.tmp"
	if julia -O2 --project="$ROOT/tools/world-bevel-jl" "$ROOT/tools/world-bevel-jl/world_bevel.jl" --map "$m" \
		--uv-mode align --min-angle 15 --smooth-models --pk3 "$tmp" >"$ROOT/benchmarks/world-$m.log" 2>&1; then
		mv -f "$tmp" "$OUT/codmod_bevel_$m.pk3"
	else
		echo "   FAILED (see benchmarks/world-$m.log)"
		fail+=("$m")
		[[ -f "$tmp" ]] && trash "$tmp"
	fi
done
echo "failed: ${fail[*]:-none}"
