#!/usr/bin/env bash
# Launch with the Goverlay "Return to Castle Wolfenstein" profile settings,
# applied directly (no bgmod/goverlay binary).
#
# Profile (from bgmod.conf):
#   GOVERLAY_MANGOHUD=1  → mangohud wrapper (OpenGL needs LD_PRELOAD, not just MANGOHUD=1)
#   gamemode=1           → gamemoderun
#   GOVERLAY_VKBASALT=0  → skipped (Vulkan-only; ioRTCW is OpenGL)
#   GOVERLAY_RESHADE=0   → skipped
#   MANGOHUD_CONFIGFILE  → scripts/MangoHud.conf (local copy of the profile HUD)
#   output_folder        → scripts/ (Shift+F2 logs; *.csv gitignored)
#
# Proton/Wine env from the profile is intentionally omitted (native ioRTCW).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_SH="$ROOT/scripts/run.sh"
SCRIPTS="$ROOT/scripts"
MANGOHUD_CONF="${MANGOHUD_CONFIGFILE:-$SCRIPTS/MangoHud.conf}"

if [[ ! -x "$RUN_SH" ]]; then
	echo "ERROR: run.sh not found at $RUN_SH" >&2
	exit 1
fi

if [[ ! -f "$MANGOHUD_CONF" ]]; then
	echo "ERROR: MangoHud config not found at $MANGOHUD_CONF" >&2
	exit 1
fi

if ! command -v mangohud >/dev/null; then
	echo "ERROR: mangohud not found in PATH" >&2
	exit 1
fi

if ! command -v gamemoderun >/dev/null; then
	echo "ERROR: gamemoderun not found in PATH" >&2
	exit 1
fi

export MANGOHUD_CONFIGFILE="$MANGOHUD_CONF"
# Required for Shift+F2 logging; keep path repo-local (no personal home).
export MANGOHUD_CONFIG="${MANGOHUD_CONFIG:+$MANGOHUD_CONFIG,}output_folder=$SCRIPTS"

# gamemoderun first (libgamemodeauto), then mangohud (shim) — both LD_PRELOADs
# survive run.sh's final exec into iowolfsp.x86_64.
exec gamemoderun mangohud "$RUN_SH" "$@"
