---
name: jev-217-adopted-safety-rules-after-a-failed-benchmark
description: On 2026-10-11, rtcw-cod adopted safety rules after a failed benchmark attempt broke the HUD and wiped the user
type: incident
date: 2026-10-11
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 217, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-11, rtcw-cod adopted safety rules after a failed benchmark attempt broke the HUD and wiped the user's binds: (1) changes to the rend2 present path, post-process or cl_scrn must be verified by the user in a real map with MSAA on, (2) the user's wolfconfig.cfg is never reset (scripts/run.sh keeps a rolling backup of 15 in run/home/codmod/cfg-backups/), (3) no workaround guardrails before finding the cause, (4) check git status in both the outer repo and the iortcw repo. An automated HUD smoke test was tried and dropped because the real flow is main menu, click, then cutscene before any HUD. Rules live in docs/testing.md.

