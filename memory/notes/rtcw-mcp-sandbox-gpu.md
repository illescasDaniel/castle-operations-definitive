---
name: rtcw-mcp-sandbox-gpu
description: RTCW MCP needs host GPU access and XDG_RUNTIME_DIR for headless gamescope
type: gotcha
date: 2026-11-16
status: current
supersedes:
superseded_by:
source:
---

The sandboxed RTCW MCP could not see the NVIDIA GPU; on the host, gamescope also failed until its server process received `XDG_RUNTIME_DIR=/run/user/1000`. For GPU tests, run the RTCW MCP with host GPU access and the actual user runtime directory. The stdio client may filter environment variables, so pass it explicitly to the server. The MCP discards launcher stderr, making early failures appear as empty engine logs. Continue to use its game lock and config guard.
