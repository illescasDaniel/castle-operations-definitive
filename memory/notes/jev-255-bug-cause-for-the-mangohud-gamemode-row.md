---
name: jev-255-bug-cause-for-the-mangohud-gamemode-row
description: "On 2026-10-16, rtcw-cod bug cause for the MangoHud GAMEMODE row (and the whole custom HUD) missing  scripts/ga"
type: incident
date: 2026-10-16
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 255, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-16, rtcw-cod bug cause for the MangoHud GAMEMODE row (and the whole custom HUD) missing: scripts/game_run.sh exported MANGOHUD_CONFIG=output_folder=..., and MangoHud 0.8.4 ignores MANGOHUD_CONFIGFILE entirely when MANGOHUD_CONFIG is set unless it contains read_cfg (overlay_params.cpp), so the default HUD was shown. Fixed by prefixing read_cfg to MANGOHUD_CONFIG.

