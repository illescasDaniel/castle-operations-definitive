#!/usr/bin/env bash
# Record the benchmark demo (mod/codmod/demos/codmod_bench.dm_50). Re-recording resets the baseline.
# Runs in a THROWAWAY home so your saves (CONTINUE), autosaves and wolfconfig.cfg are never touched.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAP="${1:-escape2}"
TMP_HOME="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME"' EXIT
cat <<EOF2
Recording in a throwaway home (fresh default config, your saves are untouched).
In the game console (~):
  god ; notarget
  record codmod_bench
  ...walk a fixed ~25-60 s route through a demanding area...
  stoprecord ; quit
EOF2
RTCW_HOMEPATH="$TMP_HOME" "$ROOT/scripts/run.sh" +set com_introplayed 1 +set g_synchronousClients 1 +spdevmap "$MAP"
mkdir -p "$ROOT/mod/codmod/demos"
cp -v "$TMP_HOME"/codmod/demos/codmod_bench.dm_* "$ROOT/mod/codmod/demos/"
echo "Now run scripts/install.sh to install the new demo."
