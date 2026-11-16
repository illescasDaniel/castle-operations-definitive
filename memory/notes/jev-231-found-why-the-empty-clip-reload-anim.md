---
name: jev-231-found-why-the-empty-clip-reload-anim
description: "On 2026-10-13, rtcw-cod found why the empty-clip reload anim sometimes never played  in cg_predict.c, weapAnim"
type: incident
date: 2026-10-13
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 231, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-13, rtcw-cod found why the empty-clip reload anim sometimes never played: in cg_predict.c, weapAnim and weapAnimTimer are carried over from the previous predicted frame (not taken from the snapshot), and ps->releasedFire / weapAnimTimer are not networked (msg.c). When the client mispredicted the last shot, the server started the reload on a command the client never replayed, so the predicted state was WEAPON_RELOADING with no WEAP_RELOAD1. Fix: after the predict loop, force RELOAD1 when the state is RELOADING; CG_RunWeapLerpFrame ignores toggle-bit-only flips of a still-playing reload (replays of the reload-start command flipped the bit every frame).

