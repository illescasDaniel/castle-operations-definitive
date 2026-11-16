---
name: jev-239-made-iortcw-the-illescasdaniel-iortcw-fork-a
description: "On 2026-10-15, rtcw-cod made iortcw/ (the illescasDaniel/iortcw fork) a git submodule of the outer codmod repo"
type: decision
date: 2026-10-15
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 239, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-15, rtcw-cod made iortcw/ (the illescasDaniel/iortcw fork) a git submodule of the outer codmod repo instead of a git-ignored clone, so each codmod commit pins the matching engine commit and `git clone --recursive` gives a working pair. Cost: every engine change needs a push to the fork plus a submodule-pointer bump commit in the outer repo; an unpushed engine commit breaks fresh recursive clones.

