---
name: jev-166-ads-iron-sight-bake-uses-absolute-per
description: On 2026-10-09, rtcw-cod ADS iron-sight bake uses absolute per-weapon cg_codAdsView rows while cod_adsTune is o
type: gotcha
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 166, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, rtcw-cod ADS iron-sight bake uses absolute per-weapon cg_codAdsView rows while cod_adsTune is on (globals folded once); saves go to run/home/codmod/codmod_ads_tune.log via cod_adsTuneSave; after bake, global iron-sight cvars default to 0 and cod_adsCrosshair becomes 2.

