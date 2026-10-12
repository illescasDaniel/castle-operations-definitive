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
