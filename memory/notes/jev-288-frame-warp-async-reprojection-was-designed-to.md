---
name: jev-288-frame-warp-async-reprojection-was-designed-to
description: "On 2026-10-24, rtcw-cod frame warp (async reprojection) was designed to replay the copied rend2 2D command tai"
type: incident
date: 2026-10-24
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 288, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-24, rtcw-cod frame warp (async reprojection) was designed to replay the copied rend2 2D command tail (SET_COLOR/STRETCH_PIC/STRETCH_PIC_GRADIENT/SWAP_BUFFERS after the main RC_POSTPROCESS) through the unchanged RB_ExecuteRenderCommands, so the present/2D path that broke the HUD before stays untouched. Gun mask is depth < 0.3 because rend2 draws the viewmodel with qglDepthRange(0, 0.3). Warp frames must not bump tr.frameCount (SMAA T2x drops history when frameCount - smaaHistoryFrame > 1). A synchronous half-rate warp (Stage 1) gives no smoothness gain over native refresh; the real gain needs cooperative GPU preemption (Stage 2). Gotchas: user default is r_aa 8 (T2x) and r_aa overrides r_ext_framebuffer_multisample (MSAA needs r_aa 5); tram spot 3826.8 1544.1 1272.1 130.0 11.4 is non-deterministic between identical runs, spot 3378 460 1104 -142 0 is stable (~0.06%); headless mcp screenshot hud=true is black and has no gun.

