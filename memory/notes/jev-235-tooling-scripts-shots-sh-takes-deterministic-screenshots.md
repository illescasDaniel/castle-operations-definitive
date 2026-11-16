---
name: jev-235-tooling-scripts-shots-sh-takes-deterministic-screenshots
description: "2026-10-14 codmod tooling  scripts/shots.sh takes deterministic screenshots of the bench demo (timedemo plus w"
type: incident
date: 2026-10-14
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 235, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-14 codmod tooling: scripts/shots.sh takes deterministic screenshots of the bench demo (timedemo plus wait N); the same build and settings give bit-identical images, and scripts/shots-diff.py compares two labels. Gotcha: with r_ssaoDepthMips 0, shot 1 reproducibly lands on a different demo frame (cause unknown), so only shots 2-6 compare for that cvar.

