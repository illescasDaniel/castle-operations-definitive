#!/usr/bin/env bash
# Idempotent workspace setup: clone ioRTCW, create run/ tree, symlink Steam pk3s + mod cfgs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IORTCW_REPO="${IORTCW_REPO:-https://github.com/iortcw/iortcw.git}"
IORTCW_COMMIT="${IORTCW_COMMIT:-438e7d413b5f7277187c35b032eb0ef9093ae778}"
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

# --- 1. Clone / pin ioRTCW ---
if [[ ! -d iortcw/.git ]]; then
	echo "Cloning ioRTCW into $ROOT/iortcw ..."
	git clone "$IORTCW_REPO" iortcw
	git -C iortcw checkout -B codmod "$IORTCW_COMMIT"
	# Apply the codmod engine changes (patches/ is the exported codmod branch).
	shopt -s nullglob
	patches=("$ROOT"/patches/*.patch)
	shopt -u nullglob
	if [[ ${#patches[@]} -gt 0 ]]; then
		echo "Applying ${#patches[@]} codmod patches ..."
		ident=()
		if [[ -z "$(git -C iortcw config user.name || true)" ]]; then
			ident=(-c user.name=codmod -c user.email=codmod@localhost)
		fi
		git -C iortcw "${ident[@]}" am --3way "${patches[@]}"
	fi
else
	current="$(git -C iortcw rev-parse HEAD)"
	if [[ "$current" != "$IORTCW_COMMIT" && "$current" != "$(git -C iortcw rev-parse --verify "$IORTCW_COMMIT" 2>/dev/null || true)" ]]; then
		# Already on codmod with local commits: leave alone.
		branch="$(git -C iortcw rev-parse --abbrev-ref HEAD)"
		echo "iortcw/ already present (branch=$branch HEAD=${current:0:12}); leaving as-is."
	else
		branch="$(git -C iortcw rev-parse --abbrev-ref HEAD)"
		if [[ "$branch" != "codmod" ]]; then
			git -C iortcw checkout -B codmod "$IORTCW_COMMIT"
		fi
		echo "iortcw/ ready (codmod @ ${IORTCW_COMMIT:0:12})."
	fi
fi

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
