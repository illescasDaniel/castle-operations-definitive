---
name: jev-225-stopped-tracking-rtcw-derived-menu-files-and
description: On 2026-10-12, rtcw-cod stopped tracking RTCW-derived .menu files and menu/hud pk3s (id game data, not GPL). G
type: decision
date: 2026-10-12
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 225, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-12, rtcw-cod stopped tracking RTCW-derived .menu files and menu/hud pk3s (id game data, not GPL). Git holds mod/codmod/menu-deltas/*.delta (our lines + replaced original line ranges, no original text); scripts/menus.py rebuilds ui/*.menu from the user's paks (SHA-256 verified) and packs the pk3s, wired into setup.sh/install.sh. Dev flow: edit ui/*.menu, run build-menus.sh --export, commit deltas. Git history still contains the old files, so rewrite/squash before publishing.

