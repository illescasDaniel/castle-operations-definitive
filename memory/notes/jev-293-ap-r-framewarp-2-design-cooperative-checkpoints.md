---
name: jev-293-ap-r-framewarp-2-design-cooperative-checkpoints
description: On 2026-10-26, rtcw-cod AP (r_frameWarp 2) design  cooperative checkpoints at render-command boundaries plus C
type: decision
date: 2026-10-26
status: current
supersedes: jev-290-frame-warp-redesign-stage-1-fixed-k
superseded_by: 
source:
---

Historical jevmem entry 293, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-26, rtcw-cod AP (r_frameWarp 2) design: cooperative checkpoints at render-command boundaries plus CPU points, warps drawn into a separate warpOutFbo with renderFbo/msaaResolveFbo pointers swapped during the unchanged 2D tail replay, because the in-progress real frame owns renderFbo and GL cannot present at a chosen time. Real frames are locked at slotRate/k (revises the 2026-10-24 "uncapped" choice: the "cannot give kT" limit applied only to mode 3's top-of-frame slots). Warp presents must not write com_lastPresentUs (bench and pace stats read it); RE_BeginFrame bumps tr.frameCount so a mid-frontend warp needs a capture-age check. Plan: docs/frame-warp-ap-plan.md.

