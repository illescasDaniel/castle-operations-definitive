#!/usr/bin/env bash
# Build ioRTCW SP (host by default; optional podman container).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USE_CONTAINER=0
TARGET=release
CLEAN=0
GAME_ONLY=0
INSTALL=0
JOBS="$(nproc)"

usage() {
	cat <<'EOF'
Usage: scripts/build.sh [--container] [--debug] [--clean] [--game-only] [--install] [-j N]

  --container   Build inside the podman image (BUILD_DIR=build-container)
  --debug       Build the debug target instead of release
  --clean       make clean before building
  --game-only   BUILD_CLIENT=0 (cgame/qagame/ui only)
  --install     Run scripts/install.sh on the output afterwards (build.sh alone leaves run/ stale)
  -j N          Parallel jobs (default: nproc)
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--container) USE_CONTAINER=1; shift ;;
		--debug) TARGET=debug; shift ;;
		--clean) CLEAN=1; shift ;;
		--game-only) GAME_ONLY=1; shift ;;
		--install) INSTALL=1; shift ;;
		-j) JOBS="$2"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
	esac
done

if [[ ! -d "$ROOT/iortcw/SP" ]]; then
	echo "ERROR: iortcw/SP missing. Run scripts/setup.sh first." >&2
	exit 1
fi

MAKE_ARGS=(-j"$JOBS" "$TARGET")
if [[ "$GAME_ONLY" -eq 1 ]]; then
	MAKE_ARGS+=(BUILD_CLIENT=0)
fi

if [[ "$USE_CONTAINER" -eq 1 ]]; then
	MAKE_ARGS+=(BUILD_DIR=build-container)
	if [[ "$CLEAN" -eq 1 ]]; then
		echo "Cleaning (container)..."
		podman-compose -f "$ROOT/container/compose.yaml" run --rm --entrypoint make builder \
			-C /src/iortcw/SP clean BUILD_DIR=build-container
	fi
	echo "Building in container: make ${MAKE_ARGS[*]}"
	podman-compose -f "$ROOT/container/compose.yaml" run --rm --entrypoint make builder \
		-C /src/iortcw/SP "${MAKE_ARGS[@]}"
	OUT_DIR="$ROOT/iortcw/SP/build-container/${TARGET}-linux-x86_64"
else
	if [[ "$CLEAN" -eq 1 ]]; then
		echo "Cleaning (host)..."
		make -C "$ROOT/iortcw/SP" clean
	fi
	echo "Building on host: make ${MAKE_ARGS[*]}"
	make -C "$ROOT/iortcw/SP" "${MAKE_ARGS[@]}"
	OUT_DIR="$ROOT/iortcw/SP/build/${TARGET}-linux-x86_64"
fi

if [[ ! -d "$OUT_DIR" ]]; then
	echo "ERROR: expected output directory missing: $OUT_DIR" >&2
	exit 1
fi

echo "Build OK. Output: $OUT_DIR"
ls -la "$OUT_DIR" || true
ls -la "$OUT_DIR/main" 2>/dev/null || true

if [[ "$INSTALL" -eq 1 ]]; then
	"$ROOT/scripts/install.sh" --build-dir "$OUT_DIR"
fi
