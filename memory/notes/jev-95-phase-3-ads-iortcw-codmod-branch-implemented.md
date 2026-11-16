---
name: jev-95-phase-3-ads-iortcw-codmod-branch-implemented
description: codmod Phase 3 (ADS, iortcw codmod branch, implemented 2026-10-08)  BG_COD_MAX_CVARS was bumped from 32 to 64
type: gotcha
date: 2026-10-08
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 95, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

codmod Phase 3 (ADS, iortcw codmod branch, implemented 2026-10-08): BG_COD_MAX_CVARS was bumped from 32 to 64 in bg_cod.h because Phase 3 alone added 19 cod_* cvars (ADS tuning + cod_adsLock/adsTune alignment tooling), bringing the total to 45. The shipped per-weapon cg_codAdsView offsets (cg_cod.c) are rough unverified guesses, not visually tuned -- no screenshot/computer-use access was used. The real tuning workflow is cod_adsLock 1; cod_adsTune 1; set cod_adsTuneRight/Fwd/Up/Pitch/Yaw/Roll ...; cod_adsTuneDump, then paste the printed initializer into cg_codAdsView in cg_cod.c.

