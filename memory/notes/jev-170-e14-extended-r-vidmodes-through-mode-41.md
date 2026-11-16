---
name: jev-170-e14-extended-r-vidmodes-through-mode-41
description: On 2026-10-09, E14 extended r_vidModes through mode 41 in ui_shared.c and both SP renderers, and the r_mode me
type: incident
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 170, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, E14 extended r_vidModes through mode 41 in ui_shared.c and both SP renderers, and the r_mode menu multi rebuilds from SDL r_availableModes when that cvar is set (otherwise the full table plus Automatic and Custom), because Item_ApplyHacks overwrites .menu mode lists and users needed 2560x1440, 3840x2160, and other high-DPI modes selectable.

