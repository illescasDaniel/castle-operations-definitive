#!/usr/bin/env bash
# Full SP audio remaster → run/codmod/codmod_hd_audio.pk3
# Locked recipe: sr_only (SFX/VO) + music sr_linked. Share this script; never the pk3.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
OUT="${OUT:-$ROOT/samples/full}"
PK3="${PK3:-$REPO/run/codmod/codmod_hd_audio.pk3}"
RECIPE="${RECIPE:-sr_only}"
MUSIC_MODE="${MUSIC_MODE:-sr_linked}"
# Resume by default so a long overnight run can continue after interrupt.
RESUME_FLAG=(--resume)
PACK_ONLY=0
NO_PACK=0
EXTRA=()

usage() {
	cat <<'EOF'
Usage: ./remaster.sh [options] [-- extra hd-audio batch args]

  (default)     Batch remaster all SP sound/ then pack codmod_hd_audio.pk3
  --pack-only   Skip batch; pack existing samples/full/game into the pk3
  --no-pack     Batch only (no pk3 write)
  --fresh       Do not --resume (reprocess every file)
  --out DIR     Batch output root (default: samples/full)
  --pk3 PATH    Destination pk3 (default: ../../run/codmod/codmod_hd_audio.pk3)
  --data DIR    Steam RTCW Main/ (or set RTCW_DATA)
  -h, --help    This help

Env: OUT, PK3, RECIPE, MUSIC_MODE, RTCW_DATA

Requires: uv, Python 3.11, NVIDIA CUDA, Steam SP paks, scripts/setup.sh once
  so run/codmod/ exists. See README.md in this directory.
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	--pack-only) PACK_ONLY=1; shift ;;
	--no-pack) NO_PACK=1; shift ;;
	--fresh) RESUME_FLAG=(); shift ;;
	--out) OUT="$2"; shift 2 ;;
	--pk3) PK3="$2"; shift 2 ;;
	--data) EXTRA+=(--data "$2"); shift 2 ;;
	-h|--help) usage; exit 0 ;;
	--) shift; EXTRA+=("$@"); break ;;
	*) EXTRA+=("$1"); shift ;;
	esac
done

cd "$ROOT"

if [[ ! -d "$REPO/run/codmod" ]]; then
	echo "Missing $REPO/run/codmod — run ./scripts/setup.sh from the repo root first." >&2
	exit 1
fi

echo "==> uv sync (Python 3.11)"
uv sync --python 3.11

if [[ "$PACK_ONLY" -eq 0 ]]; then
	echo "==> batch recipe=$RECIPE music=$MUSIC_MODE → $OUT"
	uv run hd-audio batch \
		--recipe "$RECIPE" \
		--music-mode "$MUSIC_MODE" \
		--out "$OUT" \
		"${RESUME_FLAG[@]}" \
		"${EXTRA[@]}"
fi

if [[ "$NO_PACK" -eq 0 ]]; then
	echo "==> pack → $PK3"
	uv run hd-audio pack --from "$OUT" --pk3 "$PK3"
	echo
	echo "Done. Launch with: ./scripts/run.sh +spdevmap escape1"
	echo "Do not commit or redistribute $PK3"
fi
