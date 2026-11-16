---
name: jev-282-the-dark-halos-around-badges-walls-came
description: "2026-10-23 rtcw-cod  the dark halos around badges/walls came from the HD diffuse pack (Real-ESRGAN general-wdn"
type: incident
date: 2026-10-23
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 282, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-23 rtcw-cod: the dark halos around badges/walls came from the HD diffuse pack (Real-ESRGAN general-wdn: Lanczos 4x->2x downsample adds ringing and the network darkens edges), not from normal maps (they persist with r_normalMapping 0). Fixed by regenerating with tools/hd-textures --blend 0.85 --ring-clamp 0.02 --ring-radius 1 --downsample box; user confirmed better in game. Also: models/players skins with an effect stage 0 (supersoldier, warrior zombie head, loper) can't take auto _nh because tr_shader.c picks one lit diffuse stage per shader.

