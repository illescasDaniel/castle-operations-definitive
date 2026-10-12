#!/usr/bin/env bash
# Copy built binaries into run/ (engine always; game modules to codmod, optionally main).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VANILLA=0
BUILD_DIR=""

usage() {
	cat <<'EOF'
Usage: scripts/install.sh [--vanilla] [--build-dir DIR]

  --vanilla       Also copy game .so files into run/main/ (Phase 1 only)
  --build-dir DIR Override build output (default: iortcw/SP/build/release-linux-x86_64)
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--vanilla) VANILLA=1; shift ;;
		--build-dir) BUILD_DIR="$2"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
	esac
done

if [[ -z "$BUILD_DIR" ]]; then
	BUILD_DIR="$ROOT/iortcw/SP/build/release-linux-x86_64"
fi

if [[ ! -d "$BUILD_DIR" ]]; then
	echo "ERROR: build dir not found: $BUILD_DIR" >&2
	echo "Run scripts/build.sh first." >&2
	exit 1
fi

mkdir -p "$ROOT/run/main" "$ROOT/run/codmod" "$ROOT/run/home"

ENGINE_FILES=(
	iowolfsp.x86_64
	renderer_sp_opengl1_x86_64.so
	renderer_sp_rend2_x86_64.so
)
GAME_SOS=(
	cgame.sp.x86_64.so
	qagame.sp.x86_64.so
	ui.sp.x86_64.so
)

for f in "${ENGINE_FILES[@]}"; do
	src="$BUILD_DIR/$f"
	if [[ ! -f "$src" ]]; then
		echo "ERROR: missing engine file: $src" >&2
		exit 1
	fi
	cp -f "$src" "$ROOT/run/$f"
	echo "installed run/$f"
done

for f in "${GAME_SOS[@]}"; do
	src="$BUILD_DIR/main/$f"
	if [[ ! -f "$src" ]]; then
		echo "ERROR: missing game module: $src" >&2
		exit 1
	fi
	cp -f "$src" "$ROOT/run/codmod/$f"
	echo "installed run/codmod/$f"
	if [[ "$VANILLA" -eq 1 ]]; then
		cp -f "$src" "$ROOT/run/main/$f"
		echo "installed run/main/$f (vanilla)"
	fi
done

# codmod: HUD override (phase 5b). Copy (not symlink). Never name zz_* — ioRTCW
# rewrites zz_→sp_ when resolving pak paths (see files.c FS_AddGameDirectory).
# Menu + HUD pk3s are generated (deltas + your RTCW paks), so build before copying.
"$ROOT/scripts/build-menus.sh"
if [[ -f "$ROOT/mod/codmod/codmod_hud.pk3" ]]; then
	cp -f "$ROOT/mod/codmod/codmod_hud.pk3" "$ROOT/run/codmod/codmod_hud.pk3"
	rm -f "$ROOT/run/codmod/zz_codmod_hud.pk3"
	echo "installed run/codmod/codmod_hud.pk3"
fi

# codmod: hit-marker sounds (E9). Same zz_ rename rule as the HUD pk3.
if [[ -f "$ROOT/mod/codmod/codmod_fx.pk3" ]]; then
	cp -f "$ROOT/mod/codmod/codmod_fx.pk3" "$ROOT/run/codmod/codmod_fx.pk3"
	rm -f "$ROOT/run/codmod/zz_codmod_fx.pk3"
	echo "installed run/codmod/codmod_fx.pk3"
fi

# codmod: CoD-style main menu (vertical list). Same zz_ rename rule. (pk3 built above)
if [[ -f "$ROOT/mod/codmod/codmod_menus.pk3" ]]; then
	cp -f "$ROOT/mod/codmod/codmod_menus.pk3" "$ROOT/run/codmod/codmod_menus.pk3"
	rm -f "$ROOT/run/codmod/zz_codmod_menus.pk3"
	echo "installed run/codmod/codmod_menus.pk3"
fi

# codmod: benchmark launcher cfg + recorded bench demo
if [[ -f "$ROOT/mod/codmod/codmod_bench.cfg" ]]; then
	cp -f "$ROOT/mod/codmod/codmod_bench.cfg" "$ROOT/run/codmod/codmod_bench.cfg"
	echo "installed run/codmod/codmod_bench.cfg"
fi
if [[ -d "$ROOT/mod/codmod/demos" ]]; then
	mkdir -p "$ROOT/run/codmod/demos"
	cp -f "$ROOT"/mod/codmod/demos/* "$ROOT/run/codmod/demos/"
	echo "installed run/codmod/demos/"
fi

# codmod: original pad prompt glyphs (Xbox-like / PlayStation-like). Same zz_ rename rule.
if [[ -f "$ROOT/mod/codmod/codmod_pad.pk3" ]]; then
	cp -f "$ROOT/mod/codmod/codmod_pad.pk3" "$ROOT/run/codmod/codmod_pad.pk3"
	rm -f "$ROOT/run/codmod/zz_codmod_pad.pk3"
	echo "installed run/codmod/codmod_pad.pk3"
fi

echo "install complete."
