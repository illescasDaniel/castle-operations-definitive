#!/usr/bin/env bash
# Idempotent workspace setup: init iortcw submodule, create run/ tree, symlink Steam pk3s + mod cfgs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -z "${RTCW_DATA:-}" ]]; then
	# Common Steam library locations (native, Flatpak). Override with RTCW_DATA.
	for d in \
		"$HOME/.local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main" \
		"$HOME/.steam/steam/steamapps/common/Return to Castle Wolfenstein/Main" \
		"$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main"; do
		if [[ -d "$d" ]]; then RTCW_DATA="$d"; break; fi
	done
	RTCW_DATA="${RTCW_DATA:-$HOME/.local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main}"
fi
REQUIRED_PAKS=(pak0.pk3 sp_pak1.pk3 sp_pak2.pk3 sp_pak3.pk3 sp_pak4.pk3)

cd "$ROOT"

# --- 1. Engine fork submodule (iortcw/, pinned by the outer repo) ---
if [[ ! -e iortcw/.git ]]; then
	echo "Initialising iortcw submodule ..."
	git submodule update --init --recursive iortcw
fi
echo "iortcw/ ($(git -C iortcw rev-parse --abbrev-ref HEAD) @ $(git -C iortcw rev-parse --short HEAD)); leaving as-is."

# --- 2. Runtime directories ---
mkdir -p run/main run/codmod run/home

# --- 3. Symlink required SP pk3s into run/main ---
if [[ ! -d "$RTCW_DATA" ]]; then
	echo "ERROR: RTCW data directory not found: $RTCW_DATA" >&2
	echo "Set RTCW_DATA to your Steam .../Return to Castle Wolfenstein/Main folder." >&2
	exit 1
fi

missing=0
for pak in "${REQUIRED_PAKS[@]}"; do
	src="$RTCW_DATA/$pak"
	dst="$ROOT/run/main/$pak"
	if [[ ! -f "$src" ]]; then
		echo "ERROR: missing required pak: $src" >&2
		missing=1
		continue
	fi
	ln -sfn "$src" "$dst"
	echo "linked run/main/$pak -> $src"
done
if [[ "$missing" -ne 0 ]]; then
	exit 1
fi

# --- 4. Symlink mod cfgs into run/codmod ---
for cfg in codmod.cfg codmod_binds.cfg codmod_gfxdefaults.cfg; do
	src="$ROOT/mod/codmod/$cfg"
	dst="$ROOT/run/codmod/$cfg"
	if [[ ! -f "$src" ]]; then
		echo "ERROR: missing mod config: $src" >&2
		exit 1
	fi
	# Relative symlink so the run tree stays portable within the repo.
	ln -sfn "../../mod/codmod/$cfg" "$dst"
	echo "linked run/codmod/$cfg -> ../../mod/codmod/$cfg"
done

# --- 5. Build menu/HUD pk3s from deltas + your RTCW paks (menus are not redistributed)
"$ROOT/scripts/build-menus.sh"

# --- 5b. Copy HUD override pk3 (phase 5b). Real file, not symlink — and never name it
# zz_*: ioRTCW's FS_AddGameDirectory rewrites zz_→sp_ when opening pak paths.
if [[ -f "$ROOT/mod/codmod/codmod_hud.pk3" ]]; then
	cp -f "$ROOT/mod/codmod/codmod_hud.pk3" "$ROOT/run/codmod/codmod_hud.pk3"
	rm -f "$ROOT/run/codmod/zz_codmod_hud.pk3"
	echo "installed run/codmod/codmod_hud.pk3"
fi
if [[ -f "$ROOT/mod/codmod/codmod_fx.pk3" ]]; then
	cp -f "$ROOT/mod/codmod/codmod_fx.pk3" "$ROOT/run/codmod/codmod_fx.pk3"
	rm -f "$ROOT/run/codmod/zz_codmod_fx.pk3"
	echo "installed run/codmod/codmod_fx.pk3"
fi
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

if [[ -f "$ROOT/mod/codmod/codmod_pad.pk3" ]]; then
	cp -f "$ROOT/mod/codmod/codmod_pad.pk3" "$ROOT/run/codmod/codmod_pad.pk3"
	rm -f "$ROOT/run/codmod/zz_codmod_pad.pk3"
	echo "installed run/codmod/codmod_pad.pk3"
fi

echo "setup complete."
