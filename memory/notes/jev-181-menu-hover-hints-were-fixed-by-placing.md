---
name: jev-181-menu-hover-hints-were-fixed-by-placing
description: "On 2026-10-09, codmod menu hover hints were fixed by placing yesno_message, slider_message, keyBindStatus, and"
type: decision
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 181, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, codmod menu hover hints were fixed by placing yesno_message, slider_message, keyBindStatus, and setup message_* items in a bottom hint strip (controls: rect 40 455 560 20; setup: rect 90 452 530 22), because yesno_message had stayed at vanilla mid-screen y≈320 over the CoD layout and keyBindStatus used text " " with center textalignx which offset UI_KEYBINDSTATUS ownerdraw far right and clipped the ending.

