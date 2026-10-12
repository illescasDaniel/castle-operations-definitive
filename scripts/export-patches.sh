#!/usr/bin/env bash
# Export iortcw/codmod commits as a patch series into patches/ (outer-repo backup).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${IORTCW_COMMIT:-438e7d413b5f7277187c35b032eb0ef9093ae778}"
OUT="$ROOT/patches"

if [[ ! -d "$ROOT/iortcw/.git" ]]; then
	echo "ERROR: iortcw/ missing. Run scripts/setup.sh first." >&2
	exit 1
fi

mkdir -p "$OUT"
# Remove previous series so renumbered patches don't leave stale files.
rm -f "$OUT"/*.patch

count="$(git -C "$ROOT/iortcw" rev-list --count "${BASE}..codmod" 2>/dev/null || echo 0)"
if [[ "$count" -eq 0 ]]; then
	echo "No commits on codmod beyond ${BASE:0:12}; patches/ cleared."
	# Keep an empty marker so the directory stays tracked.
	: > "$OUT/.gitkeep"
	exit 0
fi
rm -f "$OUT/.gitkeep"

git -C "$ROOT/iortcw" format-patch "${BASE}..codmod" -o "$OUT"
echo "Exported $count patch(es) to $OUT"
