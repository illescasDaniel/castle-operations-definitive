# Now
Updated: 2026-11-20

## Doing
- Renderer performance campaign: AO, geometry, specular, parallax and animated models. Profiling instrumentation is uncommitted in the engine; DOC-024 describes it.

## Done recently
- Prepared 1.1-beta for a GitHub pre-release, following 1.0-beta.
- Panini correction committed and confirmed by the user; default FOV is 100 and FOV and Gamma are under Graphics > Display.

## Next
1. Renderer perf campaign 2026-11-18 committed: 7 patches kept and enabled in mod/codmod/codmod.cfg (r_depthAttribTrim, r_sunShadowNearReuse, r_mdsShadowLod 2, r_mdsIndexCache, r_parallaxNearHit, r_parallaxRefinePar, r_specularSkip); four no-gain patches dropped (r_ssaoScalarTargets, r_depthDirectUpload, r_mdsSkinHitFastPath, r_parallaxMarchWidth). Final interleaved numbers at 1920x1200, warp 0, scale 1: origin/main 247.9 fps vs all-patches ~261-269 (session drift); reduced 7-patch set equals the 11-patch set. Benchmarks stay at 1920x1200 (user screen is 2560x1600 240Hz). Opus: GPU parallelism not worth it (GPU 94% busy). Done (uncommitted): r_postPingPong 1 removes grade_copy/sharpen_copy, +2.7% fps (A/B, ranges separate), enabled in codmod.cfg. Checked 2026-11-18, nothing more to gain safely: SSAO blur fusion needs compute shaders (engine has none, ~0.1 ms); smaa_t2x_copy_scene already skipped by r_smaaT2xPingPong; bloom has no copies. Remaining levers change visuals (r_ssaoSlices/r_ssaoSteps, blur size) and need user approval. Pending: user visual check of shadow flicker / mdsShadowLod 2 / parallax softening. Menu AF 16x only enables the filter (level r_ext_max_anisotropy, default 2).
2. User: restart the game to see the updated menus and verify them during play.
4. Flashlight/AO perf round 2026-11-20 (UNCOMMITTED in iortcw/ and outer: codmod.cfg, docs, memory). Clean 2560x1600 warp 0 scale 1 baseline: 173.2 fps flashlight off, 145.9 on. Kept r_dlightSpotMerge (+5.4% alone, flashlight on) and r_ssaoDepthInAO, both enabled in codmod.cfg; final A/B of both on the pruned build: 149.8 -> 154.0 (+2.8%) on, 169.6 -> 171.9 (+1.4%) off (noise ~3%). Dropped and removed (no gain): r_dlightSpotCull, r_flashShadowPvs, r_mdsFlashLod, r_flashMaskScissor, r_ssaoTemporal, r_ssaoFarSkip, r_ssaoBlur. cod_flashlightForce kept as a bench aid. Docs: DOC-024, DOC-010, DOC-042. Gotcha: tram spot 1 flashlight screenshots are non-deterministic (baseline vs baseline mean 2.5); use spot 2 + two baselines. Pending: user in-game check of the flashlight look and AO, then commit (submodule first, then outer pointer) and push when asked.
