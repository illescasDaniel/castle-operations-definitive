# Now
Updated: 2026-11-18

## Doing
- Renderer performance campaign: AO, geometry, specular, parallax and animated models. Profiling instrumentation is uncommitted in the engine; DOC-024 describes it.

## Done recently
- Prepared 1.1-beta for a GitHub pre-release, following 1.0-beta.
- Panini correction committed and confirmed by the user; default FOV is 100 and FOV and Gamma are under Graphics > Display.

## Next
1. Renderer perf campaign 2026-11-18 committed: 7 patches kept and enabled in mod/codmod/codmod.cfg (r_depthAttribTrim, r_sunShadowNearReuse, r_mdsShadowLod 2, r_mdsIndexCache, r_parallaxNearHit, r_parallaxRefinePar, r_specularSkip); four no-gain patches dropped (r_ssaoScalarTargets, r_depthDirectUpload, r_mdsSkinHitFastPath, r_parallaxMarchWidth). Final interleaved numbers at 1920x1200, warp 0, scale 1: origin/main 247.9 fps vs all-patches ~261-269 (session drift); reduced 7-patch set equals the 11-patch set. Benchmarks stay at 1920x1200 (user screen is 2560x1600 240Hz). Opus: GPU parallelism not worth it (GPU 94% busy). Done (uncommitted): r_postPingPong 1 removes grade_copy/sharpen_copy, +2.7% fps (A/B, ranges separate), enabled in codmod.cfg. Next: SSAO blur fusion, bloom chain, remaining smaa_t2x_copy_scene. Pending: user visual check of shadow flicker / mdsShadowLod 2 / parallax softening. Menu AF 16x only enables the filter (level r_ext_max_anisotropy, default 2).
2. User: restart the game to see the updated menus and verify them during play.
