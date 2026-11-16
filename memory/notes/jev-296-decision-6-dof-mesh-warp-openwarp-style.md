---
name: jev-296-decision-6-dof-mesh-warp-openwarp-style
description: 2026-10-28 decision  6-DoF mesh warp (OpenWarp-style) used only for AP presents; depth snapshotted at RB_WarpC
type: decision
date: 2026-10-28
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 296, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-28 decision: 6-DoF mesh warp (OpenWarp-style) used only for AP presents; depth snapshotted at RB_WarpCapture into a warp-owned linear-depth grid (renderDepthImage is overwritten by the next frame's prepass before AP warps run); translation dt measured in present time (ap.lastDoneUs - com_lastPresentUs), not sample time; velocity = delta view origin / delta refdef.time between consecutive captures; late-latch (mode 1) stays rotation-only; separate "Warp Parallax" menu row (Off/Low/Medium/High), far-side fill on by default; gun stays screen-locked. Gotchas: sky has raw depth 1.0 (treat as direction); R_WarpMatrix is new->old so forward mesh warp needs its transpose. Plan in architect report, steps M0-M3.

