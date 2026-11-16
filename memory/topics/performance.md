# performance

Imported dated observations. Configuration and implementation may have changed; check code at HEAD. Each entry retains its jevmem source ID.

## Notes

- [2026-11-05 rtcw-cod C1  r_mdsDepthTangents 0 (new cvar, default 1 = old) skips MDS tangent computation in dept](../notes/jev-305-c1-r-mdsdepthtangents-0-new-cvar-default.md) 2026-11-05
- [2026-11-05 rtcw-cod profiling  scripts/profile.sh writes profiling/<stamp>-<label>/ (mode1 r_gpuProfile 1, mod](../notes/jev-304-profiling-scripts-profile-sh-writes-profiling-stamp.md) 2026-11-05
- [2026-10-23 rtcw-cod profiler gotcha  RB_GpuMark charges the time since the previous mark to the named bucket.](../notes/jev-278-profiler-gotcha-rb-gpumark-charges-the-time.md) 2026-10-23
- [2026-10-22 rtcw-cod preference/rule  benchmarks and scripted measurement runs always run off-screen (headless](../notes/jev-270-preference-rule-benchmarks-and-scripted-measurement-runs.md) 2026-10-22
- [2026-10-22 rtcw-cod bug cause for FPS loss while moving the mouse  rend2 VaoCache (tr_vbo.c) re-memcpy'd and g](../notes/jev-269-bug-cause-for-fps-loss-while-moving.md) 2026-10-22
- [please always launch the benchmarks off-screen with the command we used on a previous session](../notes/jev-268-please-always-launch-the-benchmarks-off-screen.md) 2026-10-21
- [2026-10-22 rtcw-cod gotcha  a stale run/codmod/codmod_height_legacy.pk3 sorts after codmod_height.pk3 and sile](../notes/jev-267-gotcha-a-stale-run-codmod-codmod-height.md) 2026-10-22
- [2026-10-22 rtcw-cod rend2 parallax perf findings (architect)  with r_sunlightMode 1 the POM sun self-shadow ma](../notes/jev-266-rend2-parallax-perf-findings-architect-with-r.md) 2026-10-22
- [On 2026-10-17, rtcw-cod bug cause for specular highlights dropping bench FPS 274 -> 141  rend2 turns every ai_](../notes/jev-258-bug-cause-for-specular-highlights-dropping-bench.md) 2026-10-17
- [2026-10-14 rtcw-cod bug cause  the frame pacer's glFinish before the swap (com_maxfpsGpuSync 1, Com_PresentWai](../notes/jev-236-bug-cause-the-frame-pacer-s-glfinish.md) 2026-10-14
- [2026-10-14 codmod tooling  scripts/shots.sh takes deterministic screenshots of the bench demo (timedemo plus w](../notes/jev-235-tooling-scripts-shots-sh-takes-deterministic-screenshots.md) 2026-10-14
- [2026-10-14 rend2 gotcha  stock RB_UpdateSunFlareVis read the previous frame's sun occlusion query with a block](../notes/jev-233-rend2-gotcha-stock-rb-updatesunflarevis-read-the.md) 2026-10-14
- [On 2026-10-14, rtcw-cod found why the GPU was only ~76-80% busy uncapped  stock rend2 RB_SwapBuffers called gl](../notes/jev-232-found-why-the-gpu-was-only-76.md) 2026-10-14
- [On 2026-10-12, rtcw-cod cut the GRAPHICS options menu to a single page (Video Mode, Fullscreen, VSync, FPS lim](../notes/jev-224-cut-the-graphics-options-menu-to-a.md) 2026-10-12
- [On 2026-10-12, rtcw-cod replaced MSAA 2x with SMAA 1x High (r_smaa 3, MSAA 0) as the default AA  a rend2 pass](../notes/jev-221-replaced-msaa-2x-with-smaa-1x-high.md) 2026-10-12
- [On 2026-10-12, rtcw-cod got a frame pacer in ioRTCW (common.c Com_FrameWaitTop/Com_PresentWait/Com_PresentDone](../notes/jev-220-got-a-frame-pacer-in-iortcw-common.md) 2026-10-12
- [On 2026-10-11, rtcw-cod perf matrix (RTX 4070 Laptop, 2561x1601, MSAA2) showed the game is GPU-bound (~165 FPS](../notes/jev-219-perf-matrix-rtx-4070-laptop-2561x1601-msaa2.md) 2026-10-11
- [On 2026-10-11, rtcw-cod rebuilt its benchmark as real-time demo replay (cl_benchDemo 1 + plain `demo codmod_be](../notes/jev-218-rebuilt-its-benchmark-as-real-time-demo.md) 2026-10-11
- [On 2026-10-11, rtcw-cod adopted safety rules after a failed benchmark attempt broke the HUD and wiped the user](../notes/jev-217-adopted-safety-rules-after-a-failed-benchmark.md) 2026-10-11
- [On 2026-10-09, codmod uncapped FPS by default with seta com_maxfps "0" in mod/codmod/codmod.cfg only, because](../notes/jev-161-uncapped-fps-by-default-with-seta-com.md) 2026-10-09

