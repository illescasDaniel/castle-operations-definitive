---
name: jev-236-bug-cause-the-frame-pacer-s-glfinish
description: "2026-10-14 rtcw-cod bug cause  the frame pacer's glFinish before the swap (com_maxfpsGpuSync 1, Com_PresentWai"
type: incident
date: 2026-10-14
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 236, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-14 rtcw-cod bug cause: the frame pacer's glFinish before the swap (com_maxfpsGpuSync 1, Com_PresentWait in qcommon/common.c) serialized CPU and GPU whenever an FPS cap was set that the GPU could not hold, so a 240 cap gave about 180 FPS at ~80% GPU in gameplay while uncapped gave 225 FPS at 99%. Fixed by suspending the sync after 4 consecutive synced frames miss their deadline and retrying after 64 frames, doubling up to 2048 while retries fail.

