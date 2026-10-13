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
  --reset-binds   Full reset via codmod_binds.cfg: binds plus AA, frame limit, pacing and vsync defaults
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
	# Latch renderer cvars: +set before InitRef so the first boot matches codmod.cfg.
	# Never force r_mode/resolution (user's wolfconfig wins).
	ARGS+=(
		+set fs_game codmod
		+set cl_renderer rend2
		+set r_dlightMode 1
		+set r_ext_framebuffer_multisample 0
		+set r_floatLightmap 1
		+set r_specularMapping 1
		+set r_deluxeMapping 1
		+set r_forceSun 1
		+set r_sunShadows 1
		+set r_sunlightMode 1
		+set r_depthPrepass 1
		+set s_useOpenAL 1
		# Joystick is CVAR_LATCH — set before IN_Init so pads work on first boot.
		+set in_joystick 1
		+set in_joystickUseAnalog 1
		+exec codmod.cfg
	)
	# ADVANCED graphics cvars are latched: +set the recommended value only while wolfconfig has no saved
	# choice, so menu changes persist (otherwise codmod_binds.cfg -> codmod_gfxdefaults.cfg sets them).
	for kv in r_ext_texture_filter_anisotropic=16 r_drawSunRays=1 r_shadowFilter=2 r_shadowMapSize=2048; do
		grep -qs "^seta ${kv%%=*} " "$HOME_PATH/codmod/wolfconfig.cfg" || ARGS+=(+set "${kv%%=*}" "${kv#*=}")
	done
	# Apply default binds on first launch (no saved wolfconfig yet) or when requested.
	if [[ "$RESET_BINDS" -eq 1 || ! -f "$HOME_PATH/codmod/wolfconfig.cfg" ]]; then
		# Native desktop resolution (r_mode -2) + fullscreen; r_mode is latched, so set it before video init.
		ARGS+=(+set r_mode -2 +set r_fullscreen 1 +exec codmod_binds.cfg)
	fi
fi

# RTCW_STARTUP_SETS="cvar=value ..." (used by bench.sh --set): override a startup +set in place, or
# append it. The engine drops command-line "+" commands beyond 32 (MAX_CONSOLE_LINES), so never add
# extra lines here; latched cvars must be set on the command line to take effect at renderer init.
if [[ -n "${RTCW_STARTUP_SETS:-}" ]]; then
	declare -A OVR=()
	for kv in $RTCW_STARTUP_SETS; do OVR[${kv%%=*}]=${kv#*=}; done
	NEW=()
	for ((i = 0; i < ${#ARGS[@]}; i++)); do
		if [[ "${ARGS[i]}" == "+set" && -n "${OVR[${ARGS[i+1]:-}]+x}" ]]; then
			NEW+=(+set "${ARGS[i+1]}" "${OVR[${ARGS[i+1]}]}"); unset "OVR[${ARGS[i+1]}]"; i=$((i + 2))
		else
			NEW+=("${ARGS[i]}")
		fi
	done
	for k in "${!OVR[@]}"; do NEW+=(+set "$k" "${OVR[$k]}"); done
	ARGS=("${NEW[@]}")
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
