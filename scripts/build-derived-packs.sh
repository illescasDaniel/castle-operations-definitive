#!/usr/bin/env bash
# Build the private derived texture packs from your own RTCW paks (git-ignored, never redistributed):
#   run/codmod/codmod_zfix.pk3   texture fixes   (tools/asset-fixes/fix_assets.py, must run first)
#   run/codmod/codmod_spec.pk3   specular maps   (tools/spec-bake/spec_bake.py, reads zfix + HD pack, ~30 s)
# Incremental: a pack is rebuilt only when missing or older than its script/inputs (spec also whenever zfix was).
#   ./scripts/build-derived-packs.sh            build what is stale
#   ./scripts/build-derived-packs.sh --force    rebuild both
# Needs python3 with numpy + Pillow; if they are missing it warns and exits 0 so setup/install never fail.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

command -v python3 >/dev/null || { echo "build-derived-packs: python3 not found, skipping (texture fixes/specular pack not built)" >&2; exit 0; }
python3 -c 'import numpy, PIL' 2>/dev/null || {
	echo "build-derived-packs: numpy/Pillow missing, skipping texture fixes + specular pack (install: pip install --user numpy pillow, or your distro's python-numpy/python-pillow)" >&2
	exit 0
}

HD="$ROOT/run/codmod/codmod_hd.pk3"
PAK0="$ROOT/run/main/pak0.pk3"
ZFIX="$ROOT/run/codmod/codmod_zfix.pk3"
SPEC="$ROOT/run/codmod/codmod_spec.pk3"
FIXSRC="$ROOT/tools/asset-fixes/fix_assets.py"
SPECSRC="$ROOT/tools/spec-bake/spec_bake.py"

# stale <target> <inputs...>: true if target is missing or older than any existing input
stale() {
	local t="$1" f
	shift
	[[ -e "$t" ]] || return 0
	for f in "$@"; do
		[[ -e "$f" && "$t" -ot "$f" ]] && return 0
	done
	return 1
}

zfix_built=0
if [[ $FORCE == 1 ]] || stale "$ZFIX" "$FIXSRC" "$HD" "$PAK0"; then
	echo "building codmod_zfix.pk3"
	python3 -I "$FIXSRC"
	zfix_built=1
fi
if [[ $FORCE == 1 || $zfix_built == 1 ]] || stale "$SPEC" "$SPECSRC" "$ZFIX" "$HD"; then
	echo "building codmod_spec.pk3"
	python3 -I "$SPECSRC"
else
	echo "derived packs up to date"
fi
