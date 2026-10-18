#!/usr/bin/env bash
# Build the menu pk3s in two layers (see docs/menus.md):
#   iortcw/SP/menus/sp_zz_engine_menus.pk3   engine feature rows on RTCW's own menus (installed to run/main/);
#                                            the engine layer and its builder live in the fork (SP/menus/menudelta.py)
#   mod/codmod/codmod_menus.pk3, codmod_hud.pk3   codmod layout + mod rows on top of the engine layer
# The menus are edited versions of RTCW's own menus, so git holds only deltas (iortcw/SP/menus/deltas/ and
# mod/codmod/menu-deltas/codmod/);
# scripts/menus.py rebuilds the full files from your RTCW paks, then packs the pk3s.
#   ./scripts/build-menus.sh            build (generate missing ui files from deltas)
#   ./scripts/build-menus.sh --export   first refresh deltas from locally edited ui files (before committing):
#                                       edits in iortcw/SP/menus/ui/ -> its deltas, edits in mod/codmod/ui/ -> codmod/
# Do not rename the pk3s to zz_*: the engine renames those to sp_ (see docs/testing.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
command -v python3 >/dev/null || { echo "build-menus: python3 not found" >&2; exit 1; }
exec python3 "$ROOT/scripts/menus.py" build "$@"
