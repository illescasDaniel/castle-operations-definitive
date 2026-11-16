---
name: jev-306-bug-cause-user-s-running-game-died
description: "2026-11-05 rtcw-cod bug cause  user's running game died with SIGBUS (Misaligned address) on opening the ESC me"
type: incident
date: 2026-11-05
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 306, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-11-05 rtcw-cod bug cause: user's running game died with SIGBUS (Misaligned address) on opening the ESC menu because scripts/install.sh overwrote the mapped ui/cgame/qagame .so and pk3 files in place (cp -f) while the game ran (a coder agent ran build --install). Fixed: install.sh now copies to a temp file and renames (cp_atomic). Still avoid installing while the user plays, since they must restart to load the new build anyway.

