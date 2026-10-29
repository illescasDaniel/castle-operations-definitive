---
date: 2026-10-29
area: tool
severity: confusing
status: open
---
rtcw MCP runs end in ~2 s with 'Not connected to a server' / missing_spots when the user's wolfconfig has unlimited fps; the MCP should name that cause. Workaround: pass com_maxfps 120, com_maxfpsGpuSync 2, com_maxfpsMode 0, r_vsync 0.
