#!/usr/bin/env bash
# Build mod/codmod/codmod_menus.pk3 and codmod_hud.pk3.
# The menus are edited versions of RTCW's own menus, so git holds only deltas (mod/codmod/menu-deltas/);
# scripts/menus.py rebuilds the full files from your RTCW paks, then packs the pk3s.
#   ./scripts/build-menus.sh            build (generate missing ui files from deltas)
#   ./scripts/build-menus.sh --export   also refresh deltas from locally edited ui files (before committing)
# Do not rename the pk3s to zz_*: the engine renames those to sp_ (see docs/testing.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
command -v python3 >/dev/null || { echo "build-menus: python3 not found" >&2; exit 1; }
exec python3 "$ROOT/scripts/menus.py" build "$@"
