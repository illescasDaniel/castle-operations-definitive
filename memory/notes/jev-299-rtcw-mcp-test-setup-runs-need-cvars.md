---
name: jev-299-rtcw-mcp-test-setup-runs-need-cvars
description: "2026-10-28 rtcw MCP test setup  runs need cvars com_maxfps 120, com_maxfpsGpuSync 2, com_maxfpsMode 0, r_vsync"
type: gotcha
date: 2026-10-28
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 299, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-28 rtcw MCP test setup: runs need cvars com_maxfps 120, com_maxfpsGpuSync 2, com_maxfpsMode 0, r_vsync 0 (max 8 cvars per run) or they end in ~2 s with "Not connected to a server" because the user's wolfconfig has unlimited fps. Never use timescale 0 in the MCP console script (hangs 600 s and leaves a stale pid). Headless AP needs r_frameWarpAp 2 plus r_frameWarpApTest N. Spot "1808 1600 -759.9 0 0" on escape1 is a stable view; "3378 460 1104" is free fall.

