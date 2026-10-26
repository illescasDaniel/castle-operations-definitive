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
screenshot, save/load, map change, alt-tab); 7 menu row "Smooth (Experimental)" + docs; 8 OpenWarp mesh 6-DoF.
Interfaces: `ri.WarpCheckpoint(where,&pitch,&yaw)`, `re.WarpPresent(pitch,yaw)`, `paceGpu_t.markTag`. Dev cvars
`r_frameWarpK`, `r_frameWarpBacklogUs`, `r_frameWarpCheckpoints`, `r_frameWarpApTest`, `r_frameWarpAp` (live kill switch).

## Risks
GL state leak from mid-frame warps (most likely bug; keep checkpoints out of the velocity/prepass block), MSAA resolve
clobber, swap blocking on NVIDIA/Wayland, GPU downclock at about 87% load, k switching visible. Artefacts: HUD at real rate, gun/muzzle flash screen-locked for k presents, entity/strafe at 116 Hz.
Bigger lever if granularity fails: second shared GL context on the same thread (breaks the single-context constraint; user's call).

## Open questions
1 lock real frames at slotRate/k; 2 is 116 Hz world + 233 Hz look better than VRR uncapped 150; 3 windowed: AP off (recommended)
or oversample x1.25 (about 12% GPU); 4 slot rate 0.97 x refresh (232.8) or 237; 5 does KWin keep VRR with `r_vsync 3`; 6 ship rotation-only AP as experimental or wait for mesh 6-DoF.
