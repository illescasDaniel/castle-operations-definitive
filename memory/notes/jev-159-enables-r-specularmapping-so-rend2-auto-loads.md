---
name: jev-159-enables-r-specularmapping-so-rend2-auto-loads
description: "On 2026-10-09, rtcw-cod enables r_specularMapping so rend2 auto-loads textures/*_s as specular maps, but ships"
type: gotcha
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 159, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, rtcw-cod enables r_specularMapping so rend2 auto-loads textures/*_s as specular maps, but ships no *_s pack yet; surfaces use r_baseSpecular until a specular bake exists. Stock skies use q3map_sun not q3gl2_sun, so r_forceSun 1 is required to arm cascaded sun shadows.

