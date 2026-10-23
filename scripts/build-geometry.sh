#!/usr/bin/env bash
# One command for all the private "more geometry" packs, built from your own RTCW paks (git-ignored, never redistributed):
#   run/codmod/codmod_smooth.pk3       character bodies (MDS), tools/model-smooth/model_smooth.py
#   run/codmod/codmod_smooth_mdc.pk3   weapons, heads, props (MDC),  tools/model-smooth/mdc_smooth.py
#   run/codmod/codmod_bevel_MAP.pk3    rounded wall corners, connected textures and smoothed baked props for every map
#                                      (tools/world-bevel-jl with Julia, about 25 s for all 32 in parallel; Julia is required)
# Optional: not run by setup/install. Delete a pack to turn that part off.
#   ./scripts/build-geometry.sh              everything
#   ./scripts/build-geometry.sh --models     only the model packs
#   ./scripts/build-geometry.sh --world [MAP ...]   only the world packs (all maps, or the named ones)
# Needs python3 with numpy; Julia 1.10+ for fast world packs (docs: tools/world-bevel-jl/README.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mode=all
case "${1:-}" in --models) mode=models; shift ;; --world) mode=world; shift ;; esac
python3 -c 'import numpy' 2>/dev/null || { echo "build-geometry: python3 + numpy required" >&2; exit 1; }
if [[ $mode != world ]]; then
	echo "== character bodies"
	python3 -I "$ROOT/tools/model-smooth/model_smooth.py" --smooth '' --pk3 "$ROOT/run/codmod/codmod_smooth.pk3"
	echo "== weapons, heads, props"
	python3 -I "$ROOT/tools/model-smooth/mdc_smooth.py" --smooth 'models/*' --pk3 "$ROOT/run/codmod/codmod_smooth_mdc.pk3"
fi
if [[ $mode != models ]]; then
	echo "== world maps"
	"$ROOT/scripts/build-world.sh" "$@"
fi
