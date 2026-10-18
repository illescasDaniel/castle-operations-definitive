# Frame-perfect FPS limiter (engine level)

Goal: a frametime graph that is a **flat line** at the cap (e.g. 6.944 ms for 144),
like MangoHud `fps_limit_method=early` / RTSS / Special K, but done inside ioRTCW so it
can also fix what an external limiter cannot: the **game's own time step**.

Status: **implemented 2026-10-12** (committed). Engine work lives in `iortcw/` (`main` branch of the fork).
See "Implementation notes" at the end for what shipped and where it differs from the plan.

## 1. Why the current cap is not flat

`Com_Frame` (`iortcw/SP/code/qcommon/common.c:2697`) does:

| Problem | Effect |
|---|---|
| `minMsec = 1000 / com_maxfps` (integer ms) | 144 → 6 ms (166 fps), 165 → 6 ms; the `bias` hack then oscillates 6/7/8 ms to average out. Frametimes zig-zag by design. |
| `NET_Sleep(timeVal - 1)` + poll loop on `Sys_Milliseconds()` | 1 ms resolution wake-ups plus scheduler jitter (50–500 µs on Linux, worse on Windows). |
| `Sys_Milliseconds()` on Linux uses `gettimeofday` (`sys/sys_unix.c:184`) | Wall clock, not monotonic; NTP slews leak into frame timing. |
| Sleep happens at the **top** of the frame (before `IN_Frame`/event loop) | Equivalent to MangoHud *late*: low latency, but present time = start + variable CPU/GPU cost, so the present cadence is jittery. |
| Game time is integer ms (`com_frameTime`, `cls.realtime`, `cl.serverTime`, `usercmd.serverTime`) | Even with perfect presentation, 144 Hz frames advance game time 7,7,7,6,7,7,6… ms. Camera/animation move by uneven steps → micro-judder MangoHud can never fix. |

## 2. Design

### 2.1 Precise clock + waiter (`sys/`)

- Use the existing `Sys_Microseconds()` (monotonic on Linux via `CLOCK_MONOTONIC`, QPC on Windows).
  Add `Sys_Nanoseconds()` only if µs proves too coarse (it won't at ≤ 1000 fps).
- New `Sys_WaitUntil( int64 deadlineUs, int spinUs )`: **hybrid sleep + spin**.
  - Linux: `clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, deadline - spin)`, then spin on
    `Sys_Microseconds()` with `_mm_pause()` / `sched_yield()` until the deadline.
    Call `prctl(PR_SET_TIMERSLACK, 1)` once at startup (gamemode may already do it).
  - Windows: `CreateWaitableTimerExW(..., CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, ...)`
    (Win10 1803+, fall back to `timeBeginPeriod(1)` + `Sleep`), then spin on QPC.
  - **Adaptive spin margin**: keep a rolling P99 of sleep overshoot; `spinUs = p99 + 100 µs`,
    clamped by `com_maxfpsSpinUs` (default `-1` = auto, `0` = sleep only, `>0` = fixed).
    Spinning costs one core for ~0.2–1 ms per frame; fine on a laptop at the target caps.

### 2.2 Deadline scheduler (`qcommon/common.c`)

Replace the `minMsec`/`bias` logic (when the new limiter is on) with an absolute schedule:

```
periodUs = 1e6 / com_maxfps->value          // float cvar value, 141.5 allowed
next     = prevDeadline + periodUs           // carry fractional µs (double / fixed-point)
if ( now > next + periodUs )                 // missed by > 1 frame (hitch, load, alt-tab)
    next = now                               // re-anchor; never "catch up" with a burst
Sys_WaitUntil( next )
prevDeadline = next
```

- Absolute deadlines (not "sleep for X") mean errors don't accumulate: 144.000 fps exactly over time.
- Unfocused/minimized caps (`com_maxfpsUnfocused/Minimized`) feed the same scheduler.
- Server packets: keep a `NET_Sleep(0)` poll inside the wait loop when `com_sv_running`
  (SP runs a local server; loopback doesn't need select, but keep parity with the old loop).
- `com_timedemo` / `cl_benchDemo` timedemo path: unchanged (limiter off).

### 2.3 Where to wait: three modes (`com_maxfpsMode`)

| Mode | Wait point | Present cadence | Input latency | Analogue |
|---|---|---|---|---|
| 0 **Lowest Latency** (`start`) | top of `Com_Frame` (today's position) | jitters by render-time variance | lowest | MangoHud *late* |
| 1 **Even** (`present`) | right before `SDL_GL_SwapWindow` | flat | +~1 frame of CPU slack | MangoHud *early* (what you asked for) |
| 2 **Smart** (`predictive`, default) | top of frame at `deadline − predictedCost − margin`, plus a short pre-present wait to `deadline` | flat | close to mode 0 | Reflex / Special K "Latent Sync"-style; only possible in-engine |

- **Mode 1 hook**: `GLimp_EndFrame` lives in the renderer lib (`sdl/sdl_glimp.c:1244`). Add
  `void (*Sys_PresentWait)( void )` to `refimport_t` (`renderercommon/tr_public.h`) and call it
  right before `SDL_GL_SwapWindow`. The renderer only calls a hook; **no change to the rend2
  present/2D path** (see `docs/testing.md` safety rules). Still: user verifies HUD + pause after.
- **Mode 2 prediction**: track per-frame cost `C = present-ready time − frame start` (EMA plus a
  rolling P95 so spikes don't cause misses). Start the frame at `deadline − P95(C) − 300 µs`,
  then mode-1 wait absorbs the remainder. If a frame misses, prediction grows next frame.
- **GPU queue**: `SwapWindow` returns when the driver *queues* the frame. When the cap is above
  what the GPU can do (game is GPU-bound at ~165 fps here) CPU pacing is meaningless; the queue
  fills and frametimes follow the GPU. Rules: cap below GPU throughput; optional
  `com_maxfpsGpuSync 1` waits on a `glFenceSync` from the previous frame before starting the
  next (keeps queue depth at 1, makes predictive mode accurate). `r_finish 1` is the blunt version.

### 2.4 Frame-perfect game time (the part external limiters can't do)

Presentation is flat after 2.1–2.3, but the content still moves in integer-ms steps.

1. **Drive `msec` from the schedule, not the wake-up time.** When the limiter is on, the frame's
   time step is `deadline − prevDeadline` (exactly the period), accumulated in µs; integer `msec`
   is taken from the accumulator and the **sub-ms remainder** (`com_frameFracUs`, 0–999) is kept.
   Wake-up jitter no longer leaks into game time at all.
2. **Pass the fraction to cgame.** cgame is ours (SP, single-player only): add an argument to
   `CG_DRAW_ACTIVE_FRAME` (`client/cl_cgame.c:1062`, `cgame/cg_main.c:63`) or a trap
   `trap_GetFrameFraction()`. In cgame keep `cg.time` integer (everything depends on it) and add
   `cg.timeFrac` (0..1 ms).
3. **Use it where it is visible**, nothing else:
   - view origin: `cg.refdef.vieworg += predictedPlayerState.velocity * timeFrac/1000`
     (after `CG_PredictPlayerState`, before view bob/ADS offsets; pmove itself stays integer).
   - entity lerp (`CG_CalcEntityLerpPositions`) and `cg.frameInterpolation`: use `cg.time + frac`.
   - weapon/viewmodel bob, CoD gait/ADS timers that are visual-only.
   Guarded by `cg_subMsecLerp 1`; off = vanilla behaviour, for A/B.
4. Do **not** touch server/pmove timing, saves or demos (integer `serverTime` stays authoritative).

### 2.5 Cvars

| Cvar | Default (engine) | codmod.cfg | Meaning |
|---|---|---|---|
| `com_maxfps` | 76 (unchanged) | 0 | Read as float when the precise limiter is on |
| `com_maxfpsPrecise` | 0 | 1 | New limiter on/off (0 = exact old code path, keeps `--vanilla` identical) |
| `com_maxfpsMode` | 2 | 2 | 0 Lowest Latency (start), 1 Even (present), 2 Smart (predictive) |
| `com_maxfpsSpinUs` | -1 | -1 | spin margin: -1 auto, 0 sleep-only |
| `com_maxfpsGpuSync` | 0 | 0 → test | fence wait, queue depth 1 |
| `cg_subMsecLerp` | 0 | 1 | cgame sub-ms visual interpolation |

Note codmod ships `com_maxfps 0` (uncapped); with that, the limiter is idle. The user picks a cap
(e.g. refresh − 3 for VRR, or exactly the refresh with vsync off) in the GRAPHICS menu
("Frame rate limit" list: Off / 60 / 120 / 141 / 144 / 162 / 165 / 240 / custom).

## 3. Measurement (prove it is flat)

Extend `cl_benchDemo` (`client/cl_main.c` `CL_ReportBenchDemo`) instead of new tooling:

- Record **present timestamps** (µs, taken right after `SDL_GL_SwapWindow` via the new hook) next
  to the existing frame durations; write both to `benchmarks/last_frametimes.txt`.
- New metrics: stddev of present interval, **pacing error** = mean |interval − period|,
  % frames within ±0.1 ms / ±0.5 ms of the period, missed deadlines.
- Also log game-time step per frame (should be exactly the period with 2.4 on).
- `scripts/bench.sh --set com_maxfps 120 --set com_maxfpsMode 1` etc.; cross-check with MangoHud's
  frametime graph (`MANGOHUD_CONFIG=fps_limit=0,frame_timing=1`) and `--gpumon`.

Acceptance (laptop, 1440p-ish, cap 120 so GPU has headroom):
- present-interval stddev < 0.1 ms, ≥ 99% within ±0.25 ms, mode 2 input latency ≤ mode 0 + 1 ms
  (measure with frame-start→present delta).
- With `cg_subMsecLerp 1`: strafing past a wall in the bench demo shows no 1 ms judder
  (game-time step histogram is a single bar).

## 4. Implementation order

1. **Clock/waiter** — `Sys_WaitUntil` (unix + win32), timer slack, adaptive spin. Unit check via a
   `waittest <us> <n>` console command printing overshoot stats.
2. **Scheduler** — `com_maxfpsPrecise` path in `Com_Frame`, mode 0 only. Bench: compare vs old.
3. **Present hook** — `refimport_t.Sys_PresentWait`, mode 1. rend2 is the only renderer (opengl1 was removed).
   *User verifies HUD/pause in-game before going further.*
4. **Predictive mode 2** + optional fence sync.
5. **Game-time accumulator + `cg_subMsecLerp`** in cgame.
6. **Menu entry** (`codmod_menus.pk3` DISPLAY) + `codmod.cfg` defaults + `docs/performance.md`.
7. Linux `Sys_Milliseconds` → monotonic base (small, independent fix; can go first).

## 5. Risks

- Spinning raises CPU package power on a laptop → less GPU boost budget. Auto margin keeps spin
  short; `com_maxfpsSpinUs 0` as escape hatch.
- Present-wait is next to the swap: any mistake there looks like the old "no HUD" class of bug.
  Hook only, no FBO/blit changes; verify HUD + ESC pause per `docs/testing.md`.
- VRR/vsync: with `r_vsync 1` and cap == refresh, the swap itself blocks; Even (mode 1) is then
  redundant. Recommend vsync off + VRR + cap ≤ refresh − 3.
- Sub-ms lerp must stay visual-only; any leak into pmove/game breaks saves/demos determinism.
- `--vanilla` must be byte-identical in behaviour: everything behind `com_maxfpsPrecise 0` / `cg_subMsecLerp 0`.

## 6. Implementation notes (2026-10-12)

Code: `Sys_WaitUntil` (`sys/sys_unix.c`, `sys/sys_win32.c`), pacer (`Com_FrameWaitTop`, `Com_PresentWait`,
`Com_PresentDone`, `Com_PacedMsec` in `qcommon/common.c`), renderer hooks `ri.PresentWait/PresentDone`
(`renderer/tr_public.h`, called around `SDL_GL_SwapWindow` in `sdl/sdl_glimp.c`), cgame sub-ms in
`cgame/cg_view.c` + `cg_ents.c`. Windows path is untested.

| Cvar | Default | Notes |
|---|---|---|
| `com_maxfpsPrecise` | 0 (codmod.cfg: 1) | 0 = legacy integer-ms limiter, bit-identical `--vanilla` |
| `com_maxfpsMode` | 2 | (no menu row since 2026-10-12): 0 Lowest Latency (start of frame), 1 Even (before present), 2 Smart (predictive; lead = 2nd-worst of last 64 frame costs + 0.5 ms) |
| `com_maxfpsGpuSync` | 1 | `glFinish` before the present wait so readiness includes the GPU |
| `com_maxfpsSpinUs` | -1 | spin margin, auto |
| `cg_subMsecLerp` | 0 (codmod.cfg: 1) | view origin + entity lerp use the sub-ms remainder |
| `r_vsync` | 3 | 0 Off, 1 On, 2 Adaptive (falls back to On), 3 Triple Buffer, 4 Low Latency; applies live, no restart |

`r_vsync` modes: 3 = swap interval 0 (never blocks, newest frame wins: true mailbox behaviour only on a
compositing session such as Wayland; bare X11 can tear). 4 = swap interval 1 + `glFinish` after the swap
(queue depth 1) + frame start phase-locked to the observed vblank; if the swap does not behave like a
vblank (4 consecutive intervals outside +-12% of the refresh period) it falls back to a refresh-rate cap
using the mode-2 scheduler. `r_swapInterval` is no longer used by the SDL path.

User-facing settings (`r_vsync`, `com_maxfps`, `com_maxfpsMode`) have first-launch defaults in
`mod/codmod/codmod_defaults.cfg`, not `codmod.cfg` (which is exec'd every launch and would overwrite menu
choices). Menu rows: GRAPHICS (+ ingame copy); frame pacing lives in GRAPHICS > ADVANCED. They are reset to these defaults (together with
`r_aa`) by the menu RESET SETTINGS button, `scripts/run.sh --reset-binds` / `--reset-settings` and `/cod_resetbinds`.

Bench results (rend2, 2561x1601, cap 120, present-to-present intervals): legacy limiter 8.0 ms mean (cap not
honoured); Lowest Latency sd 629 us (65% within +-250 us); Even sd 189 us (99.0%); Smart sd 191 us (96.8%).
Bench frame timing now uses the swap timestamp (`com_lastPresentUs`).

Known limits: on this machine's Wayland (NVIDIA, 240 Hz) `r_vsync 1` did not throttle below ~350 fps in
the bench (swap interval is accepted, driver reports 1), so vsync modes 1-3 could not be validated here;
mode 4 degrades to the refresh cap. Sub-ms lerp is a small effect (<= 1 ms of motion). Not done: Windows
verification, `com_maxfpsPrecise` per-menu toggle.

### Menu labels (GRAPHICS, same rows in the in-game menu)

| Row | Cvar | Options (menu text = value) |
|---|---|---|
| Vertical Sync | `r_vsync` | Off = 0, On = 1, Adaptive = 2, Triple Buffer = 3, Low Latency = 4 |
| Frame Rate Limit | `com_maxfps` | Off = 0, 30, 60, 75, 90, 120, 144, 165, 240, 360 |

Docs and code comments use these names; the numeric values are what the cvars store.

### Menu frame rate limit (2026-10-13)

`com_maxfpsMenu` (engine default -1, `CVAR_ARCHIVE`; reset value in `codmod_defaults.cfg`): cap applied only while
`CL_InMenuOnly()` is true (main menu, intro/cinematics, pause menu = `KEYCATCH_UI` while `CA_ACTIVE`). Loading screens
and normal play use `com_maxfps` only. -1 = Auto (monitor refresh from `r_displayRefreshActual`, 60 if unknown),
0 = Off, otherwise fps; the effective cap is the lower of it and `com_maxfps`. `com_maxfps -1` also means Auto
(not the default; default stays Off). Menu list entry `"Auto (%hz)"` is expanded to the refresh rate by
`Item_Multi_Label` in `ui_shared.c`. Row "Menu Frame Rate Limit" in GRAPHICS (main + in-game menu).

## Strafe + counter-aim jitter (2026-10-14)

Symptom: strafing one way while turning the mouse the other to hold aim on a point looked jittery
(normal movement looked fine). Two camera-position timing errors that mouse look does not have:

1. `CL_SendCmd` runs before `CL_SetCGameTime`, so the newest command (and the predicted origin) is
   at the *previous* frame's `cl.serverTime`. `cg_showmiss 2` shows it: `[33150 : 33153] [33153 : 33157]`.
   The old sub-ms correction added only the current frame's fraction, so the position error alternated
   between whole 4/5 ms steps of movement every frame.
2. `CL_AdjustTimeDelta` nudges `cl.serverTime` +1 / -2 ms on snapshots (20 Hz), so a frame moves 1-2 ms
   too far or not at all.

Fix: the engine keeps a view clock (`CL_UpdateViewClock`, cl_cgame.c) that advances with the smooth
frame clock (`com_frameClockUs`: the pacer schedule, or real time uncapped) and eases 4%/frame toward
the game clock; it passes the offset to cgame as the frame fraction (can be < 0 or > 999 us now).
cgame (`cg_subMsecLerp 1`) carries the predicted view by `predictLagMs` + that offset times velocity.
A/B: `cl_viewSmooth 0` (old clock, keeps the lag fix), `cg_subMsecLerp 0` (vanilla).

### Low FPS (30) stutter (2026-10-17)

Symptom: at `com_maxfps 30` the view looked like heavy online lag; higher caps were smooth. Cause:
`cg_predict.c` zeroed `predictLagMs` when it exceeded 33 ms. A 30 FPS frame is 33.3 ms, so the lag
alternates 33/34 ms and the view extrapolation (`cg_view.c`, `velocity * (predictLagMs + timeFracUs)`)
switched off on every 34 ms frame, moving the camera back and forth by about a frame of travel.

Fix: `predictLagMs` is clamped (never zeroed) to `max(100, 3 * cg.frametime)` ms. Same pass for other
fixed short-frame thresholds: the `CL_UpdateViewClock` reset threshold is `max(15000 us, 1.5 * frame
period)`, and the `timeFracUs` validity window in `CG_DrawActiveFrame` is widened to +-100 ms. High FPS
behaviour is unchanged (lag is far below every limit). Pacer thresholds (`Com_PacedMsec`, `Com_PaceFrame`)
are already period-relative or only trip on real hitches. Not verified in-game.
