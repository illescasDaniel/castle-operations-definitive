---
name: jev-256-bug-cause-for-jack-stone-s-glasses
description: "On 2026-10-16, rtcw-cod bug cause for Jack Stone's glasses floating ~20cm above his face in OSA cutscenes (cut"
type: incident
date: 2026-10-16
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 256, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-16, rtcw-cod bug cause for Jack Stone's glasses floating ~20cm above his face in OSA cutscenes (cutscene1 etc.), rend2-only: the AO apply FBO_Blit between the opaque and translucent draw lists (tr_backend.c) left the GL viewport at full screen while the cutscene refdef was letterboxed, so translucents (h_glasses is blend, sort 5) were drawn offset from opaques. Not an MDC/VAO/frame-data bug (mesh identical across frames, opengl1 was correct). Found by bisect: r_ao=0 and r_cutsceneFx=0 fixed it, r_depthPrepass=0 did not. Fix: SetViewportAndScissor() after the blit. Letterbox bars were removed afterwards anyway.

