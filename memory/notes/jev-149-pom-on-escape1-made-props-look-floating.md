---
name: jev-149-pom-on-escape1-made-props-look-floating
description: On 2026-10-09, rtcw-cod POM on escape1 made props look floating because many castle_wall shaders are also used
type: decision
date: 2026-10-09
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 149, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-09, rtcw-cod POM on escape1 made props look floating because many castle_wall shaders are also used on floors; fix uses stage normalmap (no parallax) for floor-shared materials, mild POM only on wall-dominant leftovers, and r_parallaxMapOffset 0.5 so height is centered rather than only recessed.

