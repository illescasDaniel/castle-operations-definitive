---
name: jev-178-replaced-all-menu-item-type-slider-controls
description: On 2026-10-09, codmod replaced all menu ITEM_TYPE_SLIDER controls with ITEM_TYPE_EDITFIELD plus cvar and maxCh
type: decision
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 178, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, codmod replaced all menu ITEM_TYPE_SLIDER controls with ITEM_TYPE_EDITFIELD plus cvar and maxChars because NUMERICFIELD rejects decimal points and EDITFIELD already accepts float cvar strings without engine changes.

