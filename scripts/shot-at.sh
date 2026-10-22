#!/usr/bin/env bash
# Screenshots at fixed camera spots of one map, for A/B-checking world geometry/texture/lighting changes.
# Spots are the "setviewpos x y z yaw pitch" lines printed by the console command `viewpos`.
# wolfconfig.cfg is restored afterwards (same as shots.sh). Quits the game cleanly when done.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOME_CFG="$ROOT/run/home/codmod"
LABEL="shotat"
MAP=""
SETTLE="${SHOT_SETTLE:-400}"
WINDOWED=()
SPOTS=()
SET_ARGS=()

usage() {
	cat <<'USAGE'
Usage: scripts/shot-at.sh --map MAP [--label NAME] [--spot "x y z yaw pitch"]... [--spots-file FILE]
                          [--windowed WxH] [--set CVAR VALUE]...

  Loads MAP with cheats (spdevmap), god mode, no gun/HUD, teleports to each spot and saves
  benchmarks/shots/NAME/spotNN.tga. FILE has one "x y z yaw pitch" per line (a leading
  "setviewpos" and decimal commas are accepted; '#' lines are ignored).
USAGE
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--map) MAP="$2"; shift 2 ;;
		--label) LABEL="$2"; shift 2 ;;
		--spot) SPOTS+=("$2"); shift 2 ;;
		--spots-file) while IFS= read -r l; do [[ -n "$l" && "$l" != \#* ]] && SPOTS+=("$l"); done < "$2"; shift 2 ;;
		--windowed) WINDOWED=(--windowed "$2"); shift 2 ;;
		--set) SET_ARGS+=("$2=$3"); shift 3 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "unknown arg: $1" >&2; usage >&2; exit 1 ;;
	esac
done
[[ -n "$MAP" && ${#SPOTS[@]} -gt 0 ]] || { usage >&2; exit 1; }

CFG="$HOME_CFG/wolfconfig.cfg"
SAVED="$(mktemp)"
[[ -f "$CFG" ]] && cp -f "$CFG" "$SAVED" || : > "$SAVED"
restore() {
	[[ -s "$SAVED" ]] && cp -f "$SAVED" "$CFG"
	command -p rm -f "$SAVED" "$HOME_CFG/shotat.cfg"
}
trap restore EXIT

OUT="$ROOT/benchmarks/shots/$LABEL"
mkdir -p "$OUT" "$HOME_CFG/screenshots"
find "$OUT" -name 'spot*.tga' -delete
find "$HOME_CFG/screenshots" -name 'codmod_spot*.tga' -delete

# one command line: the engine's "wait N" defers the rest of the buffer by N frames
line="wait $SETTLE; uiclick 612 466; wait 5; uiclick; wait 30; god; notarget; set cg_drawGun 0; set cg_draw2D 0"
i=0
for s in "${SPOTS[@]}"; do
	i=$((i + 1))
	s="${s#setviewpos }"
	s="${s//,/.}"
	line+="; setviewpos $s; wait ${SHOT_WAIT:-20}; screenshot codmod_spot$(printf '%02d' "$i")"
done
line+="; wait 5; quit"
echo "$line" > "$HOME_CFG/shotat.cfg"

RTCW_STARTUP_SETS="${SET_ARGS[*]:-}" "$ROOT/scripts/run.sh" "${WINDOWED[@]}" +spdevmap "$MAP" +exec shotat.cfg >/dev/null 2>&1 || true

n=0
for f in "$HOME_CFG"/screenshots/codmod_spot*.tga; do
	[[ -f "$f" ]] || continue
	mv -f "$f" "$OUT/$(basename "$f" | sed 's/codmod_//')"
	n=$((n + 1))
done
echo "saved $n screenshot(s) to $OUT"
