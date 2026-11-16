---
name: jev-226-menu-deltas-moved-to-format-v2-scripts
description: "On 2026-10-12, rtcw-cod menu deltas moved to format v2 (scripts/menus.py)  any run of lines present in an RTCW"
type: decision
date: 2026-10-12
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 226, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-12, rtcw-cod menu deltas moved to format v2 (scripts/menus.py): any run of lines present in an RTCW original (base or other menu) is stored as `=<pak path> a b` with a `#src sha256` header instead of literal text, so git holds no original menu passages (only ~75 distinct one-line property assignments with different indentation, plus braces). Round-trip verified byte-identical. ui/menus.txt and ingame.txt remain tracked near-verbatim lists. Also: Ani4K model now downloads from Sirosky/Upscale-Hub, hit-marker wavs and pad glyphs are documented as original (Claude-generated tones / original art) in docs/credits.md.

