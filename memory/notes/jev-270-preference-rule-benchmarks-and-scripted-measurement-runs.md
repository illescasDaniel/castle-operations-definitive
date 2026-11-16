---
name: jev-270-preference-rule-benchmarks-and-scripted-measurement-runs
description: 2026-10-22 rtcw-cod preference/rule  benchmarks and scripted measurement runs always run off-screen (headless
type: decision
date: 2026-10-22
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 270, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-22 rtcw-cod preference/rule: benchmarks and scripted measurement runs always run off-screen (headless gamescope). scripts/bench.sh now does this by default (BENCH_ONSCREEN=1 opts out); shots use SHOT_HEADLESS=1; scripts/spin-test.sh is the view-motion smoke test (still vs turning GPU time ratio, fails above 1.25x). Documented in AGENTS.md and docs/performance.md.

