#!/usr/bin/env bash
# Archive what produced a profiling session into the given directory: git SHAs and dirty diffs of both repos,
# SHA-256 of the executables / modules / demo that run, installed pk3 names + sizes (no pack content), the mod cfgs and
# GPU info. Private packs are only listed, never copied.
# Usage: scripts/profile-env.sh OUT_DIR
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:?usage: profile-env.sh OUT_DIR}"
mkdir -p "$OUT"
{
	echo "date: $(date -Is)"
	echo "outer: $(git -C "$ROOT" rev-parse HEAD) $(git -C "$ROOT" describe --always --dirty 2>/dev/null || true)"
	echo "engine: $(git -C "$ROOT/iortcw" rev-parse HEAD) $(git -C "$ROOT/iortcw" describe --always --dirty 2>/dev/null || true)"
	echo "host: $(hostname) $(uname -sr)"
} > "$OUT/versions.txt"
git -C "$ROOT" status --short > "$OUT/outer.status.txt" || true
git -C "$ROOT/iortcw" status --short > "$OUT/engine.status.txt" || true
git -C "$ROOT" diff > "$OUT/outer.diff" || true
git -C "$ROOT/iortcw" diff > "$OUT/engine.diff" || true
{
	find "$ROOT/run" -maxdepth 2 \( -name 'iowolfsp*' -o -name 'renderer_*' -o -name '*.so' \) -type f -print0 2>/dev/null | sort -z | xargs -0 -r sha256sum
	[[ -f "$ROOT/run/codmod/demos/codmod_bench.dm_50" ]] && sha256sum "$ROOT/run/codmod/demos/codmod_bench.dm_50"
} | sed "s#$ROOT/##" > "$OUT/sha256.txt" || true
find "$ROOT/run" -maxdepth 2 -name '*.pk3' -printf '%p %s bytes %TY-%Tm-%Td\n' 2>/dev/null | sed "s#$ROOT/##" | sort > "$OUT/packs.txt" || true
for f in codmod.cfg codmod_defaults.cfg codmod_tuning.cfg codmod_gfxdefaults.cfg; do
	[[ -f "$ROOT/mod/codmod/$f" ]] && cp -f "$ROOT/mod/codmod/$f" "$OUT/$f"
done
nvidia-smi -q > "$OUT/nvidia-smi.txt" 2>/dev/null || true
echo "environment archived in $OUT"
