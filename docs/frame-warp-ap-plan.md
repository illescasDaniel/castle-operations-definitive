# Compositor mode (`r_frameWarp 2`, "AP") plan, architect report 2026-10-26

Status: planned, nothing built. Gate: user go-ahead for step 1.

## Mechanism
Single thread, single GL context, in-order GPU queue. Warps are inserted at **cooperative checkpoints**: render-command
boundaries in `RB_ExecuteRenderCommands` (sun-shadow cascades are separate `RC_DRAW_SURFS`), 2-3 audited points inside
`RB_DrawSurfs` (after prepass/depthcopy, after SSAO, after `scene_opaque`), and CPU points (top-of-frame wait, after
`SV_Frame`, before `SCR_UpdateScreen`). Warps are drawn into a separate `tr.warpOutFbo`; for the 2D tail replay
`tr.renderFbo`/`msaaResolveFbo` are swapped temporarily so `RB_SwapBuffers` and the 2D code stay byte-identical.
There is no GL API to present at a chosen time: slot error is about the GPU chunk in front of the warp (1-1.6 ms at
native; largest headless chunks: sunshadow 1.19 ms, scene_opaque 0.88 ms at 1920x1200). Acceptable only with **VRR in
fullscreen** and no present interval below 1/refresh.

## Decisions
1. Backlog bounded at each checkpoint (mid-frame about 1000 us; end of backend P98 frontend CPU + 500 us).
2. Insert a warp at the first checkpoint where predicted completion >= lastWarpDone + Tmin (Tmin = 1/refresh + 100 us).
3. Real frames locked at slotRate/k (k = ceil(slotRate / sustainable real fps), k=2 about 116 real fps, 233 Hz presents).
   Revises the 2026-10-24 "real frames uncapped" choice: the "cannot give kT" limit applied only to mode 3 (top-of-frame
   slots). Free-running about 130 would judder (1,2,1,2 presents). k=1 is plain LL. Hysteresis: up after 4 misses, down
   after 2 s with >= 15% headroom. In AP `com_maxfps` means the presented rate. Slot rate = cap if 0 < cap <= refresh else
   0.97 x refresh (`r_frameWarpHz` override stays).
4. LL is the base layer (first warp after a capture). The LL-1 GPU drain must be off in mode 2.
5. Requires fullscreen, `com_maxfpsGpuSync 2`, `r_vsync` 0-3. Windowed or `r_vsync 4`: deny with printed reason, fall back to LL.
6. Warp presents must not write `com_lastPresentUs`, `ps.siv`, `latch.swapLat` (bench reads `com_lastPresentUs`): add `com_lastWarpPresentUs`.
7. Capture-age check instead of `frameCount == tr.frameCount` (`RE_BeginFrame` bumps it). Warp always drawn even under 0.01 deg.

## Trade-off to tell the user
Rotation-only AP gives 233 Hz look but world, translation and entities drop from about 150 to about 116 Hz. Whether
that beats VRR uncapped at 150 is a feel question. Fallback if the spike fails: LL + VRR fullscreen + fence pacer capped at a rate the GPU holds (120-141).

## AP-0 spike (steps 1-4, k forced 2, real frames still present normally)
`apstats` (also at bench end): warp-present GPU cost, checkpoint gap P50/P98, warp-to-warp interval P2/P50/P98, slots
served %, sample->GPU completion P50/P98, SDL_GL_SwapWindow CPU P98, real fps.
Headless go (1920x1200, `r_frameWarp 2 r_frameWarpHz 233 com_maxfpsGpuSync 2`, gpuprof): warp GPU P98 <= 0.5 ms (x1.78 for
native), checkpoint gap P98 <= 1.6 ms, real fps >= 99% of cap, uncapped loss <= 12%. Correctness: `r_frameWarpApTest 1`
(zero-delta warp at every checkpoint) must be bit-identical to off in `compare_shots` at `3378 460 1104 -142 0` for `r_aa` 4, 5, 8.
User gate (fullscreen VRR): interval P2 >= 1/refresh - 0.1 ms, P98 <= 1/refresh + 1.2 ms, slots served >= 95%, swap CPU
P98 <= 0.3 ms, latency spread (P98-P50) <= 1 ms; monitor refresh readout under `r_vsync` 3 and 1; A/B of AP k=2 vs VRR uncapped vs cap 116 + LL.

## Steps (`scripts/build.sh --install`)
A (parallel): 1 interfaces + tagged GPU mark ring (`tr_public.h`, `tr_pacegpu.c`); 2 warp present (`tr_warp.c`,
`tr_local.h`, `tr_init.c`: `warpOutFbo`, `RE_WarpPresent`, state save/restore, recursion guard, gpuprof must not end frame).
Then 3 backend checkpoints (`tr_backend.c`; compare_shots identical for `r_frameWarp 0/1`); 4 scheduler (`common.c`,
`cl_main.c`, `scripts/bench.sh`; **user gate: AP-0 verdict**); 5 adaptive k + denies + suspension (**user gate**);
6 optional: skip real tail so every present is a scheduled warp (changes present semantics: **user gate** HUD, ESC, console,
screenshot, save/load, map change, alt-tab); 7 menu row "Smooth (Experimental)" + docs; 8 OpenWarp mesh 6-DoF (done, user-verified 2026-10-28: `r_frameWarpMesh`, menu row "Warp Parallax", see `docs/frame-warp.md`).
Interfaces: `ri.WarpCheckpoint(where,&pitch,&yaw)`, `re.WarpPresent(pitch,yaw)`, `paceGpu_t.markTag`. Dev cvars
`r_frameWarpK`, `r_frameWarpBacklogUs`, `r_frameWarpCheckpoints`, `r_frameWarpApTest`, `r_frameWarpAp` (live kill switch).

## Risks
GL state leak from mid-frame warps (most likely bug; keep checkpoints out of the velocity/prepass block), MSAA resolve
clobber, swap blocking on NVIDIA/Wayland, GPU downclock at about 87% load, k switching visible. Artefacts: HUD at real rate, gun/muzzle flash screen-locked for k presents, entity/strafe at 116 Hz.
Bigger lever if granularity fails: second shared GL context on the same thread (breaks the single-context constraint; user's call).

## Open questions
1 lock real frames at slotRate/k; 2 is 116 Hz world + 233 Hz look better than VRR uncapped 150; 3 windowed: AP off (recommended)
or oversample x1.25 (about 12% GPU); 4 slot rate 0.97 x refresh (232.8) or 237; 5 does KWin keep VRR with `r_vsync 3`; 6 ship rotation-only AP as experimental or wait for mesh 6-DoF.

## User answers (2026-10-27)
1 yes, lock real frames at slotRate/k. 2 windowed/borderless: fall back to late-latch. 3 slot rate: advised 0.97 x refresh
(about 233 on 240 Hz) with VRR; caps at 240/120/60 are for fixed-refresh sync and are not needed with VRR. 4 rotation-only AP
is independent of the mesh 6-DoF warp, so build it now as experimental; 6-DoF follows (it fixes translation/entity judder
on warp frames). 5 assume KWin keeps VRR with `r_vsync 3` fullscreen (unverified; user sees no tearing).
Housekeeping 2026-10-27: main merged into frame-warp in both repos (iortcw 68df2504, outer dad535e); feature/geometry
verified fully merged in main and deleted locally; `run/codmod/codmod.cfg` was a stale regular copy pinning
`com_maxfpsGpuSync "1"`, re-symlinked to `mod/codmod/codmod.cfg` (pins 2) as `setup.sh` does.

## Cap rule (user, 2026-10-27; overrides the plan's "com_maxfps means the presented rate")
Slot rate = 0.97 x the display refresh (rounded down, e.g. 233 / 116 / 58 for 240 / 120 / 60 Hz), computed from the actual
refresh, never hard-coded. Active only while `r_frameWarp 2` is really running: the pacer ignores the in-game `com_maxfps`
internally without writing the cvar, so the saved menu cap is untouched and applies again as soon as AP is off or falls back
to late-latch (windowed, `r_vsync 4`, denied). The dev override `r_frameWarpHz` stays. `r_frameWarp 0/1` pacing unchanged.

## Setting conflicts (user, 2026-10-27): last change wins, with a console line
- `r_frameWarp` set to 2 while `r_vsync` is 4: set `r_vsync` 3.
- `r_vsync` set to 4 while `r_frameWarp` is 2: set `r_frameWarp` 1 (keep late-latch).
- Windowed/borderless is not auto-changed: AP denies itself and falls back to late-latch with a printed reason.
- Implement with the step 7 menu row (both menu layers; rows must reflect the change), in the engine cvar-modified path.

## Rate controller instead of integer k (2026-10-27)
k is fixed at 2 (`r_frameWarpK` still forces another k and a fixed S). The slot rate S adapts in [60, 0.97 x refresh]
(real = S/2, 30 real fps minimum): 3 missed real frames in a row (or smoothed interval/period > 1.12) lower S by 8%; after 3 s
without misses, a probe raises S by 4% when the median frame cost leaves ~10% of the new real period spare, kept after 90
clean frames, else reverted with a 2/4/8..60 s back-off. S is slewed 1.5% per real frame (warm window of 6 frames after any
change). At S_min with misses AP denies itself 15 s ("GPU cannot hold compositor budget", late-latch) and restarts mid range.
One printed line per 2 s at most (`slot rate A -> B (real R)`). Scheduler guard added: at most k-1 warps per real period
(plus one per overdue slot while the real frame is late); without it, after a load drop the scheduler produced 1.7 warps per
real frame (about 238 presents/s at S 170). `r_frameWarpEarly` (default 0) lets a warp be placed a fraction of a slot
early; it did not help served% and stays off.

## Deny rule, statistics and start-up rework (2026-10-29, `common.c`)
Why: the stats stored a real frame's GPU completion, not its swap time (the fence is queued before the present hold), so
present intervals of held frames were wrong ("served%" said 95% while ~45% of intervals were under half a slot, and the
old deny never fired); in `com_maxfpsMode 0` the deadline is the frame start, so the miss counter flagged nearly every frame.
- **Present time**: a real frame's done entry is `max(GPU done, swap return)` (`paceRec_t.swapUs`, stamped in
  `Com_PresentDone`); warps keep their GPU time. Busy time, the rate controller and `lastDoneUs` stay on GPU done.
- **`apstats`**: `served%` is gone. New: `distinct_per_s`, `distinct_iv_p98` (a present counts as distinct only when at
  least `r_frameWarpDenyMinGap` x T1 after the last counted one, on sorted times), `ll_est_fps`, `fe_p50/p98` (frame
  start -> first backend command), `hold_mean` (real present hold, us). `denies_slower_ll`, `denies_gpu_hold`.
- **Deny** (`Com_ApDenyCheck`): per 3 s window of clean running (the clock and the present collection pause on
  non-clean frames, they do not restart), deny when distinct presents/s < `r_frameWarpDenyGain` (1.10) x the late-latch
  estimate, unless P98 of the counted intervals is above 1.6 x k x T1 (a hitch, not a verdict; the guard uses the real period
  because a healthy k = 2 run has P98 of about 2 T1). Estimate (`Com_ApLLEstimate`) = min(user cap if > 0, refresh
  (`r_frameWarpHz` stands in for it), 1e6 / late-latch GPU busy, 1e6 / late-latch CPU frame time P90, and while fresh (< 60 s)
  1e6 / the measured baseline interval); the busy time falls back to AP's own busy minus (k-1) warp costs. Message:
  `AP delivered X/s vs late-latch Y/s (gain G): AP off for N s` (G = X / Y). Deny time doubles on repeats (30 s .. 5 min).
  The "GPU cannot hold S_min" rule is unchanged.
- **Baseline hygiene**: late-latch frames now measure the first backend command (the checkpoint hook runs before the
  `ap.running` return), so they give GPU busy time (`llBusyEma`) and front-end time. The baseline (interval, busy, CPU
  time) only updates when `CL_WarpDeny()` was NULL at the frame start (stored on the record), and is reset when the
  `mapname` cvar changes. The "measuring the late-latch baseline" wait only counts time the client allows the warp.
- **Start-up** (`Com_ApSeedRate`, `r_frameWarpSeed` 1): S0 = clamp(k x 0.88 x 1e6 / max(llBusy + (k-1) x warpCost,
  cpuP90 x k / 2), S_min, S_max) instead of S_max (no late-latch busy samples yet: S_max); first start warms 30 frames
  (was 60); a restart after > 3 s on the same map returns to the last S that held 5 s, never above the new seed; no upward
  probe in the first 5 s. The 0.92 / 0.88 / 0.80 thresholds are unchanged.
- **Pacing phase independent of `com_maxfpsMode`**: while AP runs the pacer uses mode 2 internally (cvar untouched):
  the present is held to the deadline and the frame starts a lead early, lead = max(PaceLead + 500, (T - T1) + fe P98 +
  warp cost), at most 0.9 T, i.e. at or before W - fe P98 - warp cost with W = previous deadline + T1. So the mid-period
  warp lands in the backend, not in the front-end gap or the present hold. The deadline is now the present target in every
  mode, which makes the miss counter (`Com_ApNoteReal`, statistics only) meaningful.
- **Fixed on the way**: the first AP start could run a checkpoint in its top-of-frame wait before the GPU clock mapping
  existed; marks then resolved against `calOff` 0, `lastDoneUs` was poisoned for good and no warp was ever placed (only visible
  when AP starts once, cleanly). `Com_ApUpdate` now calibrates when the mapping is unset; `Com_ApBacklog` is clamped.
- Internal cvars (code defaults only, never in a menu or cfg): `r_frameWarpDenyGain` 1.10, `r_frameWarpDenyMinGap` 0.5,
  `r_frameWarpSeed` 1.

### Empirical deny (2026-10-29 follow-up 2)

The formula/LL-sample estimate misjudged the real late-latch rate in play (said 191/s, real ~125/s), so it no longer
denies. When the advisory estimate says AP < r_frameWarpDenyGain x estimate (3 s clean window, >100 presents, P98
guard as before), AP runs a 2 s late-latch trial (client must allow warping; any client deny aborts it with a 10 s
back-off), measures the real late-latch distinct presents/s (first 0.5 s ignored) and compares it with AP's distinct/s
from the window before. Deny (30 s, doubling to 5 min) only if measured LL x gain >= AP; otherwise AP resumes and the
next trial waits 60 s (doubling to 16 min on repeated keeps). One line prints both numbers. r_frameWarpDenyGain 0 =
never deny by comparison. The GPU-cannot-hold-S_min rule is unchanged.

### Seed headroom and one-step overload (2026-10-29)

`Com_ApSeedRate` now adds 12% headroom to the busy estimate and uses late-latch busy samples only if the last one is
under 20 s old (otherwise S_max). The overload step takes the full computed target `0.88*k*1e6/busyEma` (the old 0.98
clamp never bound: the target is already below 0.96 x S; the floor is 0.5 x S instead of 0.7).

### Diagnostics and trial hysteresis (2026-10-31, `common.c`)

**Same-clock counters.** Every present is also stamped with its CPU swap-return time (`aps.sdone`, parallel to the GPU
series). New `apstats` lines: swap-clock kinds/hist/distinct, warp actual minus predicted completion, warp lateness vs
previous real swap + T1, swap-return minus raw GPU done (warp / real), hold target vs resulting interval, trial counters
(started/kept/denied/aborted). `apstats timeline [s]` prints 250 ms buckets (S, distinct, warps, reals, decl reasons, busy
mean/max, misses, sleeps, trial state); `apstats dump` writes `apdump.txt` (timeline + both present series) to the homepath
game dir. Rings are 32768 presents (~140 s).

**Finding (headless escape1, 1920x1200, r_aa 8, mesh 3, S 233, 119 s):** the r>w / w>r asymmetry of the GPU-clock series
(w>r 3573 us, r>w 5025 us) is mostly timestamp skew. A real present is stamped at its swap return, which is ~1.9 ms after
its GPU done (p50 +1.93 ms); a warp is stamped at its GPU done, ~1.0 ms after its swap return (p50 -1.03 ms). On the swap
clock the pair is w>r 4618 / r>w 3979 us (mean T1 = 4292): residual +-0.3 ms, opposite sign. Warps are not late (p50 -0.38 ms
vs previous real swap + T1), the hold lands 0.14-0.35 ms after its target, warp prediction error p50 +0.12 ms (p2/p98
-0.38/+0.84 ms). The true on-screen time lies between the two clocks. Unloaded run: distinct 224/s, 0 trials.

**Trial hysteresis.** A trial starts only when AP < 1.0 x estimate in 2 consecutive clean windows, never while probing or
while the slot rate slews; first keep backoff 120 s (doubles to 16 min as before). The verdict still uses
`r_frameWarpDenyGain` against the measured late-latch rate. Dev cvar `r_frameWarpDenyForceLL <fps>` (default 0 = off)
replaces the estimate (headless caps it at ~117). Headless checks: normal estimate, 119 s: no trial; forced 1000: trial,
measured LL 121/s vs AP 227/s, kept, next trial in 120 s; forced 1000 with `r_frameWarpHz 116`: AP 111/s vs LL 121/s,
denied 30 s, second trial 108 vs 120, denied 60 s.

### Asymmetric slot-rate controller: fast down, slow up (2026-10-31, `common.c` `Com_ApUpdate`)

Why: in heavy views the busy time swings 8.2-8.9 ms; the old EMA(16) test (down at 0.92 x period, re-aim 0.88, probe up
at < 0.80 of the new period) crossed its threshold all the time, so S ratcheted down to the heaviest moments and crept
back (baseline scenario: 26 downs+ups per 100 s). Delaying the reaction (parked staircase patch) made it worse; this
keeps the down reaction fast and removes the thrash on the way up.
- **Down**: decided on P90 of the last 48 real-frame busy times (`Com_ApBusyP90`; the ring is cleared with every
  retarget, 20 samples needed). P90 > 0.95 x real period, or 3 consecutive misses with P90 > 0.90, steps S straight to
  `r_frameWarpDownAim` (0.85) x k x 1e6 / P90 (at least 3% down, floor 0.5 x S); at most one step per 1 s. The
  0.95 / 0.85 gap is the hysteresis band. A load step is seen after about 5-20 heavy frames (measured: busy step at
  t = 66.75 s, target reached by 67.5 s, i.e. under 1 s including the 1.5%/frame slew).
- **Up**: only when P90 stays under 0.85 x the real period of the next rung (S x 1.05) continuously for
  `r_frameWarpUpCalm` (15 s), never within 10 s of a step down; one 5% rung per calm. A probe is kept after 150 real
  frames; if the overload test fails at the new rate it reverts, the calm needed doubles (up to 240 s), and the next
  up waits 10 s. A kept probe resets the calm. Start-up (`Com_ApSeedRate`), the GPU-cannot-hold-S_min rule and the
  empirical deny are unchanged.
- **Cvars (internal, code defaults only)**: `r_frameWarpUpCalm` 15, `r_frameWarpDownAim` 0.85.
- **Side fix**: a real frame whose GPU work finished before its present hold ended was harvested before its swap was
  stamped, so its distinct-present entry sat at the GPU time right behind the following warp (`Com_ApFixDone` moves it to
  the swap time afterwards). Reduces, but does not remove, the GPU-clock skew below.

### Distinct presents on the swap-return clock (2026-10-31 follow-up)

The "GPU-clock skew" found above was the cause of the false trials: a real frame whose GPU work ends well before its present
hold is stamped at its GPU completion, right behind the warp that follows it, so the pair counted as one present
(AP read ~110-175/s in a heavy view while the swap returns were evenly spaced). Everything that judges AP's delivered rate now
uses the **swap-return clock** (a warp's and a real present's `SDL_GL_SwapWindow` return, the same clock as the late-latch
trial's presents): the deny window (`ap.winT`, fed from `Com_ApWinSwap` at both swap sites), the `AP delivered X/s` lines,
`apstats` `distinct_per_s`/`distinct_iv_p98`, and the `apstats timeline` / dump `dist=` buckets. The GPU-completion version stays
in `apstats` as `gpuclk_distinct_per_s` (and the `iv_*`, `kinds`, `hist` lines of the first block are still GPU-clock); the
swap-clock kinds line prints `swap_distinct_per_s`. `Com_ApFixDone` (moves an early-harvested real frame's GPU-clock entry to
its swap time) stays for the diagnostic series.

Numbers (headless 1920x1200, r_aa 8, escape1, S0 233, load 3200 = 8.3 ms vs 5.1 ms, default deny settings):

| | before (EMA controller, GPU clock) | after |
|---|---|---|
| 10 s wave, 60 s: downs+ups per 100 s | 26.3 (7 downs, 10 ups, 10 probes) | 1.5 (1 down, 0 ups) |
| S in heavy / light | 202-213 / 233 (stepping) | 208 / 208 |
| bucket distinct/s median, P5, ratio | 196, 116, 0.59 (GPU clock) | 208, 200, 0.96 (swap clock; GPU clock gave 0.55) |
| misses / sleeps (span) | 55 / 5 (64.5 s) | 38 / 5 (67.9 s) |
| distinct_per_s final (swap / GPU clock) | n/a | 206.1 / 175.7 |
| swap-return interval std | 686 us | 614 us |
| 30 s phases (heavy/light/heavy/light, 135 s) | n/a | 4 changes (2.96 per 100 s), ratio 0.96, no trial, per-phase distinct/s 205-208 |
| unloaded, 80 s | 224/s, 0 downs | 227.3/s, 0 downs, no trial |
| mild swing (r_gpuLoad 1500 vs 0) | n/a | S 233 throughout, 0 downs/probes (run before the clock change) |

The 30 s run (no `r_frameWarpDenyGain 0`) no longer gets the false "AP slower than late-latch" trial: AP delivers ~205/s on
the swap clock against a late-latch estimate of 120/s (headless, `com_maxfps` 120). Its sequence: 233 -> 207 at the first
heavy step, 207 -> 218 -> 229 in the light phase (15 s calm per rung), 229 -> 218 revert + 203 in the second heavy phase,
203 -> 213 in the last light phase. Raw logs of these runs were kept outside the repo (scratchpad).
