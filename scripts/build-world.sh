#!/usr/bin/env bash
# Build the private world packs (corner bevel + baked-prop smoothing) for all maps, or the named ones, with
# tools/world-bevel-jl. Output: run/codmod/codmod_bevel_MAP.pk3 (git-ignored, derived from RTCW maps). See tools/world-bevel-jl/README.md.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/run/codmod"
maps=("$@")
if [[ ${#maps[@]} -eq 0 ]]; then
	mapfile -t maps < <(python3 -I -c "
import glob, zipfile
names = set()
for p in glob.glob('$ROOT/run/main/*.pk3'):
    with zipfile.ZipFile(p) as z:
        names.update(n[5:-4] for n in z.namelist() if n.startswith('maps/') and n.endswith('.bsp') and '/' not in n[5:])
print('\\n'.join(sorted(names)))")
fi
mkdir -p "$ROOT/benchmarks"
if ! command -v julia >/dev/null; then
	echo "julia not found (1.10+ required), see tools/world-bevel-jl/README.md" >&2
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
