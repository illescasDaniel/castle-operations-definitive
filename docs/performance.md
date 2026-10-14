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

Ruled out (no change): non-blocking sun-flare query (`RB_UpdateSunFlareVis`), `__GL_MaxFramesAllowed=3`,
XWayland vs native Wayland, depth read as `GL_UNSIGNED_INT`. The CPU is not the limit here (720p:
~2.2 ms/frame vs 4 ms GPU at 2561x1601). Metrics come from `bench.sh --gpumon` (nvidia-smi SM %).
Tradeoff: without the per-frame finish the CPU may queue up to the driver's limit (2-3 frames) ahead when
uncapped, so uncapped input latency can be a frame or two higher; a cap or `r_vsync 4` avoids that.
