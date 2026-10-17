# Performance benchmark

Measures per-frame cost on a fixed, recorded route. Benchmark only: it does not change rendering,
the present path, or any saved cvar (see "Safety rules" in `docs/testing.md`).

## How it works

`mod/codmod/demos/codmod_bench.dm_50` is a recorded SP demo (~23 s). It is replayed at **real time**
(plain `demo`, `cl_benchDemo 1`, `com_maxfps 0`) and every rendered frame is timed in microseconds
(`Sys_Microseconds`, `CL_SetCGameTime`). The first 2 s are skipped as warm-up (asset/shader loading).

Stock `timedemo 1` is **not** used: it advances a fixed 50 ms of game time per frame, so the demo
collapses into ~500 frames in a few seconds, which is too few for 1% lows and unlike real play.

## Running

CLI (3 runs by default; run 1 is a warm-up and excluded from the median; quits by itself):

```bash
./scripts/bench.sh --label baseline [--runs N] [--mangohud] [--windowed 1280x720]
```

Menu: main menu -> OPTIONS -> GRAPHICS -> **RUN BENCHMARK**. When the demo ends the game
returns to the main menu and "Last run:" shows the summary (`cl_benchSummary`).

`bench.sh` runs at the user's own resolution/graphics settings, backs up `wolfconfig.cfg` and restores it
afterwards. It appends to `benchmarks/results.csv` (gitignored) and keeps each run's frame times in
`benchmarks/<date>-<label>-runN.txt` (header = stats + res/MSAA/swap/maxfps).

## Metrics

| Field | Meaning |
|---|---|
| `avg_fps` | frames / seconds |
| `low1_fps` | FPS of the slowest 1% of frames, averaged |
| `median_ms`, `p95_ms`, `p99_ms`, `max_ms` | frame-time percentiles |
| `hitches` | frames over 3x the median |

Prefer **1% low / P99 / hitches** over average FPS. Compare only runs with the same demo, resolution
and graphics settings; the log warns if vsync (`r_swapInterval`) or a `com_maxfps` cap is active.
Run-to-run noise is real (GPU clocks, shader cache): use 3+ runs and compare medians.

## Re-recording the demo

`./scripts/record-bench-demo.sh [map]` (default `escape2`) runs in a throwaway home (`RTCW_HOMEPATH` in `run.sh`), so saves, CONTINUE and `wolfconfig.cfg` are untouched: `record codmod_bench`, walk a fixed route,
`stoprecord`. It copies the demo to `mod/codmod/demos/`. Re-recording resets all baselines.

## Findings (2026-10-11, RTX 4070 Laptop, 2561x1601, MSAA 2, rend2 defaults)

Options: `bench.sh --set CVAR VALUE` (repeatable), `--env K=V`, `--gpumon` (nvidia-smi SM/mem %). Overrides go
into `run/home/codmod/bench_override.cfg` plus a startup `+set` substitution in `run.sh`
(`RTCW_STARTUP_SETS`); the engine only keeps 64 `+` command-line commands (was 32, and `run.sh` used all 32).
Baseline: 165-167 avg FPS, 1% low 111-113, P99 8.3 ms, run-to-run spread under 1% when nothing else
uses the GPU (earlier 79/97 FPS numbers were taken while other GPU work was running).

**Verdict: GPU-bound** (GPU ~78% busy; 1280x720 gives 328 FPS, ~3 ms CPU floor).

| Change (median of 2 measured runs) | avg FPS | 1% low | vs base 165 |
|---|---|---|---|
| `r_depthPrepass 0` (kills sun light + SSAO + shadow mask, not a pure optimization) | 222 | 141 | +34% |
| `r_forceSun 0` (no sun shadows/rays/SSAO) | 223 | 146 | +35% |
| `r_ext_framebuffer_multisample 0` | 211 | 134 | +28% |
| `r_ssao 0` | 186 | 87 | +13% |
| `r_shadowMapSize 1024` | 180 | 121 | +9% |
| `r_drawSunRays 0` | 171 | 110 | +3% |
| `r_shadowFilter 1` | 170 | 110 | +3% |
| `r_specularMapping 0`, `r_dlightMode 0` | 166 / 165 | 111 / 94 | 0% |
| `r_sunShadows 0` alone | 160 | 99 | 0% (cascades still render) |
| `__GL_THREADED_OPTIMIZATIONS=1` | 165 | 110 | 0% |
| 1280x720 | 328 | 163 | +99% |

Engine experiment, **rejected**: non-blocking sun-flare occlusion query (`RB_UpdateSunFlareVis`): 164 FPS, no gain
because the frame is GPU-bound. Nothing in the list is a free (visually identical) win; the big costs are the
visual features themselves. For more FPS, trade quality knowingly (MSAA, SSAO, shadow map size/filter).

## SMAA vs MSAA (2026-10-12)

Bench demo, 2561x1601, RTX 4070 Laptop, idle GPU, median of 3 measured runs (run 1 warm-up).

| Config | Avg FPS | 1% low | P99 ms |
|---|---|---|---|
| MSAA 2x (old default) | 190.4 | 119.6 | 7.48 |
| SMAA 3 High (new default) | 225.4 | 132.8 | 6.52 |
| SMAA 4 Ultra | 220.8 | 139.3 | 6.67 |
| No AA | 261.2 | 147.9 | 6.00 |

SMAA High costs ~0.6 ms/frame vs ~1.4 ms for MSAA 2x: **+18% FPS** over the old default. Credits: [credits.md](credits.md).

## GPU utilisation: 76% -> 97% (2026-10-14)

Uncapped, the GPU was only ~76-80% busy (nvidia-smi / MangoHud) although the game is GPU-bound. Two CPU/GPU
sync points in stock rend2 left it idle every frame:

1. **`glFinish()` in `RB_SwapBuffers`** (stock Q3, runs whenever `r_finish 0`). The CPU waited for the GPU to
   go idle, then did the next frame's game/front-end work while the GPU had nothing queued. Now off
   (`r_swapFinish 0`, default; `1` = stock). The driver's frame queue bounds how far ahead the CPU runs; with a
   cap or `r_vsync 4` the frame pacer still syncs (`com_maxfpsGpuSync`).
2. **Flare/corona depth readback** (`RB_TestFlare`): one `glReadPixels` of the depth buffer per flare (~3 a
   frame in the bench demo) drained the GPU pipeline. Reading into a pixel pack buffer with a fence did **not**
   help (the depth read itself stalls on this driver). Replaced with per-flare `GL_SAMPLES_PASSED` occlusion
   queries (a one-pixel depth-tested quad at the flare's depth minus the stock 24-unit tolerance), read only
   once available; visibility lags 1-2 frames, hidden by the fade. `r_flaresAsync 1` (default; `0` = stock).
   Flare renders per frame match the stock path (1.58 vs 1.56).

Bench demo, 2561x1601, SMAA 3, `r_ao 4`, median of 2 measured runs:

| Config | avg FPS | 1% low | P99 ms | GPU busy |
|---|---|---|---|---|
| Before (stock) | 183 | 106 | 7.60 | 76% |
| `r_swapFinish 0` | 219-227 | 145 | 6.1 | 87-90% |
| + flares via PBO + fence (rejected) | 223-227 | 146 | 6.1 | 88-91% |
| + flares via occlusion queries (**shipped**) | **247** | **163-167** | **5.4** | **97%** |
| `r_flares 0` (reference ceiling) | 249 | 165 | 5.5 | 97% |

Ruled out (no change at the time): non-blocking sun-flare query (`RB_UpdateSunFlareVis`; it did pay off later, see
the next section), `__GL_MaxFramesAllowed=3`,
XWayland vs native Wayland, depth read as `GL_UNSIGNED_INT`. The CPU is not the limit here (720p:
~2.2 ms/frame vs 4 ms GPU at 2561x1601). Metrics come from `bench.sh --gpumon` (nvidia-smi SM %).
Tradeoff: without the per-frame finish the CPU may queue up to the driver's limit (2-3 frames) ahead when
uncapped, so uncapped input latency can be a frame or two higher; a cap or `r_vsync 4` avoids that.

## GPU pass profiling: 247 -> 303 FPS, same image (2026-10-14)

`r_gpuProfile 1` (`tr_gpuprof.c`) times each render pass with GPU timestamp queries, read a few frames later without
blocking. The table prints with the `gpuprof` command (`gpuprof reset` clears it) and at renderer shutdown, so a
`bench.sh --set r_gpuProfile 1` run leaves it at the end of `run/home/codmod/rtcwconsole.log`
(`grep "codmod gpuprof"`). Columns: average ms per 3D frame, share of GPU frame time, worst frame, % of frames that
ran the pass.

Image checks: `scripts/shots.sh --label NAME [--set CVAR VALUE]` takes 6 deterministic screenshots of the bench demo
(`timedemo` steps 50 ms of game time per frame; the same build and settings gives bit-identical shots), and
`scripts/shots-diff.py A B` prints per-shot differing pixels and max difference, and writes amplified diff PNGs.
Caveat: with `r_ssaoDepthMips 0`, shot 1 reproducibly lands on a different demo frame (cause unknown; other cvars do
not do this), so compare shots 2-6 for that cvar.

Changes, each measured with the profiler (ms of GPU time per frame) and checked with shots:

1. **Sun flare query no longer blocks** (`RB_UpdateSunFlareVis`, tr_postprocess.c). Stock code read last frame's
   sun occlusion query with a blocking `GL_QUERY_RESULT`, a CPU/GPU sync every frame the sun is in front of the view.
   Now a 4-query ring, read when available. Side effect: the stock code's result was usually not ready and counted as
   visible, so the sun-ray passes ran on almost every frame even indoors; now they run only when the sun is visible
   (5-10% of the bench demo). Same image (0 differing pixels).
2. **No tone-map/SMAA copies.** SMAA reads the tone-mapped scratch image and writes straight to the scene FBO,
   instead of a copy before and after it. Same image.
3. **SMAA weights on edge pixels only** (`r_smaaStencil 1`): the edge pass marks edge pixels in a stencil buffer and
   the blend-weight pass skips everything else, as in the reference SMAA. `smaa_weights` 0.145 -> 0.052 ms. Same image.
4. **GTAO depth mips** (`r_ssaoDepthMips 1`): far GTAO taps read a point-sampled mip of the half-res depth (XeGTAO's
   trick; level n once the tap is more than 2^(n+3.3) px away). Per-pixel random directions made the far taps miss
   the texture cache: constant noise was 2.4x faster. `ssao_ao` 0.78 -> 0.49 ms (+0.03 ms to build the mips). Not
   bit-exact but visually identical: vs before, 1.3-3.8% of pixels differ, nearly all by 1-2/255; worst 25/255 on a
   1-px depth edge where SMAA's edge detection flipped.
5. **AO upsample with `textureGather`** (ssaoup_fp.glsl): 2 gathers instead of 8 fetches for the 4 AO and depth
   texels. `ssao_apply` 0.258 -> 0.201 ms. Same image.

Bench demo, 2561x1601, SMAA 3, `r_ao 4`, `r_vsync 3`, RTX 4070 Laptop:

| Build | avg FPS | 1% low | GPU ms/frame |
|---|---|---|---|
| Before (engine 0b6f57fc) | 247 | 165 | ~4.07 |
| + 1, 2 | 281 | 184 | 3.45 |
| + 3, 4, 5 (**shipped**) | **303** | **175** | **3.21** |

1% low varies by +-10 between runs; avg FPS repeats within ~1%. Profile after (ms): scene 0.51, ssao_ao 0.49,
sun cascades 0.42, sun shadow mask 0.27, ssao_apply 0.20, smaa_blend 0.18, tone-map 0.13, smaa_edges 0.13, depth
prepass 0.12, ssao_depth 0.13, depth copy 0.10, 2 AO blurs 0.10 each, present 0.07.

Left as is: the remaining passes are the visual features doing real work. Removing the full-res depth copy
(`hdrDepth`, 0.1 ms) would mean sampling the depth texture while it is attached to the FBO being drawn (a GL
feedback loop). Cascade 3 (whole level) is already cached until the sun moves.

## Frame cap below the cap (2026-10-14)

With a cap set (`com_maxfps`, e.g. 240 = monitor refresh) that the GPU cannot hold, FPS fell well below uncapped
(gameplay: 180 FPS / ~80% GPU at a 240 cap vs 225 FPS / 99% uncapped). Cause: the frame pacer's `glFinish`
before the swap (`com_maxfpsGpuSync 1`, `Com_PresentWait` in common.c) serializes CPU and GPU every frame,
the same stall as the stock `RB_SwapBuffers` finish. It is useful when the cap is reachable (frame timing sees
the GPU, lower latency), so it is now adaptive: after 4 synced frames in a row finish past their deadline the
sync is suspended, and retried after 64 frames, doubling (up to 2048) while retries keep failing.

| Bench demo, 2561x1601 | avg FPS | 1% low |
|---|---|---|
| cap 240, sync always (before) | 211 | 136 |
| cap 240, sync off | 239.5 | 160 |
| cap 240, adaptive (**shipped**) | 239.3 | 160 |
| cap 144, adaptive (sync stays on) | 144.0 | 123 |
| cap 280 (above the GPU), adaptive | 250 | 174 (uncapped: ~254) |

## Specular cost (2026-10-17)

`r_codSpecular 1` (spec maps + light-grid specular + cubemaps) took the bench demo from 274 to 141 FPS (median frame
unchanged, p95 3.8 -> 13 ms, hundreds of hitches). `r_speeds 1` showed batches/frame 600 -> 3500 with the same
surfaces and verts: with no `misc_cubemap` entities rend2 uses every `ai_marker` as a probe (164 on escape2), and the
per-surface `cubemapIndex` is not in the draw sort key but ends a batch whenever it changes. The `sunshadow` GPU pass
(not fill-bound, unchanged by shadow map size) went 0.4 -> 4.1 ms because shadow/depth views drew one batch per
surface. Disabling any one of deluxe specular or spec maps hid it (batch splitting needs a probe on lit surfaces).

Fixes (engine `iortcw/SP/code/rend2`):
1. `R_AddDrawSurf` zeroes the cubemap for shadow/depth views, unlit shaders and (with `r_cubemapSpecOnly 1`, default)
   shaders without a spec map (`shader_t.useCubemap` / `hasSpecMap`); `RB_RenderDrawSurfList` ignores it in depth fill;
   `R_RadixSort` gets a stable cubemap pass so equal keys group per probe.
2. `R_ClusterCubemaps`: ai_marker probes merged within `r_cubemapMergeDist` (384u, latched): 164 -> 33 on escape2
   (also ~5x faster map load).
3. `lightall_fp.glsl`: uniform branches skip the spec-map fetch and cubemap block when not bound.

Bench (escape2 demo, 2561x1601): spec off 274 FPS, spec on before 141, after 267 (0 hitches; batches 3500 -> 517).
Fix 1 alone gives 266; 2 and 3 add load time and a little GPU. Spec-map VRAM was not the issue (not reduced).

### Camera-following specular hotspot (2026-10-17)

Symptom: close to metal, a bright spot follows the view as if the player held a flashlight (flashlight off).
Cause: BSP surfaces take their light vector from `R_LightDirForPoint` (`tr_light.c`), which falls back to the surface
normal when the light-grid direction faces away (dot <= 0.2). `lightall_fp.glsl` normalises that vector into `L` and
applies `CalcSpecular(..., pow(roughness, r_deluxeSpecular))` to the whole lightmap colour, so with `L == N` and the
camera looking head-on (`E ~ N`), `H ~ N` and `NH ~ 1`: a tight hotspot exactly where the camera looks. The
`lightColor /= max(surfNL, 0.25)` compensation boosts it up to 4x. Ambient-dominated grid cells behave the same way.

Fix: `R_LightDirForPoint` now stores the vector with length `0.25 + 0.75 * (directed/(directed+ambient))^r_codSpecDirectional`
(exactly 0.25 on the normal fallback). The shader reads `|L|` before normalising and scales only the baked-light
specular by `clamp((|L| - 0.25) / 0.75, 0, 1)`. Diffuse is unchanged (L is still normalised); no new fetches or
uniforms. Sun/primary light, dynamic lights and the flashlight (`USE_LIGHT_VECTOR` and primary paths) are untouched.
`r_codSpecDirectional` (non-archived, default 1; read at map load, so reload the map) is the exponent: 0 = old
behaviour, 1 = linear, 2 = stricter. Cubemap reflections are separate (probe-baked, not camera-dependent).
