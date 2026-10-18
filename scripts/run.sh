#!/usr/bin/env bash
# Launch ioRTCW SP from the run/ tree (codmod by default, or --vanilla).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/run"
# RTCW_HOMEPATH: use a throwaway home (saves/config/demos) instead of run/home, e.g. for recording.
HOME_PATH="${RTCW_HOMEPATH:-$RUN/home}"
VANILLA=0
RESET_BINDS=0
WINDOWED=""
EXTRA_ARGS=()

usage() {
	cat <<'EOF'
Usage: scripts/run.sh [--vanilla] [--reset-binds|--reset-settings] [--windowed WxH] [engine args...]

  (default)       Run with fs_game codmod
  --vanilla       Run with fs_game main (no codmod)
  --reset-binds   Full reset via codmod_defaults.cfg: binds plus every user-facing setting (AA, frame limit, vsync, ...)
  --reset-settings  Same as --reset-binds
  --windowed WxH  Windowed mode, e.g. 1280x720
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--vanilla) VANILLA=1; shift ;;
		--reset-binds|--reset-settings) RESET_BINDS=1; shift ;;
		--windowed)
			WINDOWED="$2"
			shift 2
			;;
		-h|--help) usage; exit 0 ;;
		*) EXTRA_ARGS+=("$1"); shift ;;
	esac
done

ENGINE="$RUN/iowolfsp.x86_64"
if [[ ! -x "$ENGINE" ]]; then
	echo "ERROR: engine not found at $ENGINE" >&2
	echo "Run scripts/setup.sh && scripts/build.sh && scripts/install.sh --vanilla" >&2
	exit 1
fi

# Rolling backup of the saved config (binds, display, prefs) before every launch,
# so a bad session or tool can never destroy it. Keeps the newest 15 distinct copies.
CFG_DIR="$HOME_PATH/codmod"
CFG_BAK="$CFG_DIR/cfg-backups"
if [[ -f "$CFG_DIR/wolfconfig.cfg" ]]; then
	mkdir -p "$CFG_BAK"
	last="$(ls -t "$CFG_BAK"/wolfconfig-*.cfg 2>/dev/null | head -1 || true)"
	if [[ -z "$last" ]] || ! cmp -s "$CFG_DIR/wolfconfig.cfg" "$last"; then
		cp -f "$CFG_DIR/wolfconfig.cfg" "$CFG_BAK/wolfconfig-$(date +%Y%m%d-%H%M%S).cfg"
	fi
	ls -t "$CFG_BAK"/wolfconfig-*.cfg 2>/dev/null | tail -n +16 | xargs -r rm -f --
fi

ARGS=(
	+set fs_basepath "$RUN"
	+set fs_homepath "$HOME_PATH"
	+set vm_game 0
	+set vm_cgame 0
	+set vm_ui 0
	+set sv_pure 0
	+set logfile 2
)

if [[ "$VANILLA" -eq 0 ]]; then
	# Everything else comes from the engine's mod hooks (Com_ExecuteCfg): codmod_defaults.cfg before
	# wolfconfig.cfg (first-launch values), codmod.cfg after it (pinned values), both before video/input init.
	ARGS+=(+set fs_game codmod)
	# Reset: re-apply the user-facing defaults. Startup "+exec" runs after wolfconfig.cfg (the "+set" lines
	# are consumed earlier), so it overwrites the saved choices; latched ones (r_mode...) apply on vid_restart.
	if [[ "$RESET_BINDS" -eq 1 ]]; then
		ARGS+=(+exec codmod_defaults.cfg)
	fi
fi

# RTCW_STARTUP_SETS="cvar=value ..." (used by bench.sh/shots.sh --set): force cvars for this launch. The engine
# applies startup +set after all configs (codmod_defaults.cfg, wolfconfig.cfg, codmod.cfg) and before renderer
# init, so they win, latched cvars included. The engine drops "+" commands beyond MAX_CONSOLE_LINES.
if [[ -n "${RTCW_STARTUP_SETS:-}" ]]; then
	for kv in $RTCW_STARTUP_SETS; do ARGS+=(+set "${kv%%=*}" "${kv#*=}"); done
fi

if [[ -n "$WINDOWED" ]]; then
	if [[ ! "$WINDOWED" =~ ^([0-9]+)x([0-9]+)$ ]]; then
		echo "ERROR: --windowed expects WxH, e.g. 1280x720 (got: $WINDOWED)" >&2
		exit 1
	fi
	W="${BASH_REMATCH[1]}"
	H="${BASH_REMATCH[2]}"
	ARGS+=(+set r_fullscreen 0 +set r_mode -1 +set r_customwidth "$W" +set r_customheight "$H")
fi

cd "$RUN"
exec ./iowolfsp.x86_64 "${ARGS[@]}" "${EXTRA_ARGS[@]}"
