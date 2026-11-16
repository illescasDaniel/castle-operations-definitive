---
name: jev-285-bug-cause-white-holes-in-bevelled-maps
description: "2026-10-23 rtcw-cod bug cause  white holes in bevelled maps (escape1) come from rounding convex edges  foreign"
type: incident
date: 2026-10-23
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 285, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-23 rtcw-cod bug cause: white holes in bevelled maps (escape1) come from rounding convex edges: foreign surface touching the edge mid-run, two solids touching diagonally along one edge line, or a box-vertex mitre with a sharp third edge. Fixed by reject_touched_edges! in tools/world-bevel-jl/src/bevel2.jl; build-world.sh is Julia-only (Python tool lacks the fix), 8 maps parallel, deflate level 6.

