---
name: jev-145-escape1-sigsegv-with-codmod-hd-pk3-was
description: "On 2026-10-09, escape1 SIGSEGV with codmod_hd.pk3 was ResampleTexture stack overflow  p1 1024 /p2 1024  overfl"
type: incident
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 145, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, escape1 SIGSEGV with codmod_hd.pk3 was ResampleTexture stack overflow: p1[1024]/p2[1024] overflowed for 2048+ HD TGAs. Fixed in iortcw/SP/code/renderer/tr_image.c and rend2/tr_image.c by Hunk_AllocateTempMemory(outwidth). Rebuild/install renderer .so (not game-only) after this change.

