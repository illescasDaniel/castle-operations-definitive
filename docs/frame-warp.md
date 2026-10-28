# Frame warp (asynchronous reprojection)

Branch `frame-warp` (both repos). Engine feature, default off. Goal: present at the display rate (e.g. 120 Hz) while
rendering every k-th refresh, re-projecting the last real frame to the latest look direction (rotation only, 3-DoF).

## How it works
- **Capture** (`rend2/tr_warp.c`, `RB_WarpCapture`, one gated line at the end of `RB_PostProcess`): final main-view
  scene to `tr.warpImage` (rgb) with a gun mask in alpha (depth < 0.3, the viewmodel depth range), plus a copy of the
  2D command tail (SET_COLOR / STRETCH_PIC / STRETCH_PIC_GRADIENT / SWAP_BUFFERS). A non-main view later in the same
  frame must not clobber the capture (fixed).
- **Warp frame** (`RE_WarpFrame`, exported as `re.WarpFrame`): homography pass into `tr.renderFbo`, then the saved tail
  goes through the unchanged `RB_ExecuteRenderCommands` (HUD + present untouched). Does not bump `tr.frameCount`
  (SMAA T2x history).
- **Look delta** (`CL_PeekLookDelta`, `cl_input.c`): queued mouse events (`Com_PeekMouseEvents`, not consumed) scaled
  like `CL_MouseMove`, plus the last cmd's pad/gyro/keyboard turn rate extrapolated. `CL_WarpAllowed`/`CL_WarpDeny`
  gate it (menus, cutscenes, loading, dead, MG42, third person, paused, recording).
- **Pacer** (`common.c`, `Com_WarpActive` / `Com_WarpFrameWaitTop` / `Com_WarpSlot` / `Com_WarpPresentWait`): real
  frame every k*T, k-1 warp presents in the slots between; suspends with backoff when real frames do not fit in T.

## Cvars and commands
`r_frameWarp` (`CVAR_ARCHIVE | CVAR_LATCH`, default 0; user setting: GRAPHICS > DISPLAY row "Frame Warp" with three levels, Off (0) / Low latency (1, late-latch) / Smooth (Experimental) (2, compositor "AP"), in both layers, main and in-game variants; applies through the menu's Apply button = soft `vid_restart`, which re-runs `R_Init` -> `R_WarpInitTargets`; codmod first-launch/Reset value `seta r_frameWarp "0"` in `codmod_defaults.cfg`; Off is exactly the old behaviour and the row never writes `com_maxfps`/`com_maxfpsMode`/`r_vsync`), `r_frameWarpHz` (0 = auto refresh; test override),
`r_frameWarpMaxDeg` 20, `r_frameWarpGunDepth` 0.3, `r_frameWarpGunDilate` 1, debug `r_warpDebug` 1/2/3 +
`r_warpDebugPitch/Yaw`. Commands `warpstats`, `warprstats`.

## Warp Parallax (mesh 6-DoF warp, `r_frameWarpMesh`)
Only affects the compositor presents of Smooth (`r_frameWarp 2`); with Off or Low latency it has no effect, so the menu row
is greyed out and not clickable (`cvarTest "r_frameWarp"` + `disableCvar { "0" "1" }`) unless Frame Warp is Smooth. The greying
follows the ACTIVE `r_frameWarp` (the UI reads the live string, not the pending latched one), so it updates after Apply;
the row's own value is kept while greyed. It replaces the rotation-only reprojection of the warp presents by an OpenWarp-style mesh warp: the real
frame's depth is captured as a grid, each warp present moves the grid vertices by the camera rotation plus the camera
translation predicted over the elapsed time (velocity x dt), and the frame is drawn as a triangle mesh. This removes the
strafe blur (judder of near geometry at 116 Hz presents) that rotation-only AP shows. User-verified at level 2 on
2026-10-28.
- Cvar `r_frameWarpMesh` (`CVAR_ARCHIVE | CVAR_LATCH`, code default 0 = vanilla): 0 off, 1/2/3 = depth grid step 16 / 8 / 4
  px. Menu: GRAPHICS > DISPLAY row "Warp Parallax" (Off / Low / Medium / High -> 0 / 1 / 2 / 3), directly below Frame Warp,
  in both layers and both variants (main and in-game); applies through Apply (soft `vid_restart`) like Frame Warp.
  Codmod first-launch/Reset value `seta r_frameWarpMesh "2"` in `codmod_defaults.cfg` (menu Reset path = `execmodcfg`).
- Cost: raster-bound by triangle count. Low = about -20% mesh draw
  versus Medium; the mesh adds about 0.06-0.07 ms per warp at 1920x1200 (about 0.11 ms estimated at
  2560x1600). Total warp GPU at 2560x1600 measured p50 0.46 ms / p98 0.81 ms (rotation-only about 0.25 ms).
- Live A/B cvars (no restart): `r_frameWarpMeshTranslate` (1; 0 = rotation only), `r_frameWarpMeshFill` (1; fill
  disocclusion holes), `r_frameWarpMeshStretch` (2.0; max triangle stretch before it is discarded),
  `r_frameWarpMeshMaxMove` (16; max applied translation in world units), `r_frameWarpMeshMaxSpeed` (1500; speed in units/s
  above which velocity counts as a teleport and translation is dropped). Dev: `r_frameWarpMeshDt` (> 0 overrides the
  predicted warp dt in ms), `r_warpDebug 4` (mesh visualisation), `r_warpDebugMove "x y z"` (cheat; fixed translation).
- Known limits: moving actors update at the real frame rate (the mesh only knows camera motion); translucent surfaces
  move with what is behind them (depth of the opaque layer); a halo shows at thin foreground objects (fill smears the
  background); the gun stays screen-locked; a brief lag at jump start (velocity has not built up yet).

## Levels, AP requirements and setting conflicts
- Levels of the one `r_frameWarp` row: 0 Off, 1 Low latency (late-latch), 2 Smooth (Experimental) = AP compositor
  (`docs/frame-warp-ap-plan.md`).
- AP runs only with: fullscreen, `r_vsync` 0-3 (3 recommended), `com_maxfpsGpuSync 2`, `com_maxfpsPrecise 1`. When a
  requirement is missing AP denies itself with a printed reason and falls back to late-latch (windowed is not
  auto-changed).
- Conflicts, last change wins, each with a console line (`Com_FrameWarpConflicts`, `common.c`, checked every frame
  against the pending latched `r_frameWarp` value): `r_frameWarp` set to 2 while `r_vsync` is 4 sets `r_vsync` 3;
  `r_vsync` set to 4 while `r_frameWarp` is 2 sets `r_frameWarp` 1. A saved 2 + 4 combination at startup keeps AP
  and sets `r_vsync` 3. The change is only in the archived cvars (normal saving); `r_frameWarp` still applies with the
  menu's Apply (vid_restart).

## Limits
Stage 1 is synchronous: a real frame must fit in T minus the warp cost, so by itself it does not make 80 FPS feel like
120 (a machine that fits could render at native rate). The real gain is Stage 2: cooperative preemption (warp present
inserted between render commands of the next real frame). Only camera rotation gets smoother; edges smear in fast turns.
Headless runs have no mouse, so warp frames look identical to real ones; headless timing is slow (warp works at
`r_frameWarpHz 20`).

## Late-latch spec (`r_frameWarp 1`), stage LL

Decision (2026-10-24, see `memory/decisions.md`): ship late-latch first, alone, without the fixed-k pacer.

- `r_frameWarp` stays `CVAR_ARCHIVE|CVAR_LATCH`, range 0..3: 0 off, 1 late-latch, 2 smooth (adaptive pacer, later),
  3 legacy fixed-k Stage 1 (dev only). `Com_WarpActive` (the fixed-k pacer) is true only in mode 3, so mode 1 touches
  no pacing.
- One warp per real frame inside `RB_PostProcess`, right after `RB_WarpCapture` (`tr_backend.c`, the gated call near
  the end): `RB_WarpLatch` calls `ri.WarpLatch(gpuWait, &pitch, &yaw)` (absolute view angles, qfalse = denied), then
  `RB_WarpApply` warps into `renderFbo`; the unchanged 2D tail and `RB_SwapBuffers` follow. Skip the warp when the
  delta is under ~0.01 degrees. No 2D/present code changes. SMAA T2x history is copied at `smaa_copy` before the
  capture: confirm nothing else reads `renderFbo` across frames.
- Input reference: `CL_PeekLookDelta` (delta since last usercmd) is wrong once the next `CL_CreateCmd` ran. Add
  `re.WarpSetRef(cl.viewangles)` called from `cl_main.c` before `SCR_UpdateScreen`; `RB_WarpCapture` copies the ref
  into `tr.warp.refAngles`. At warp time the client returns absolute angles
  `cl.viewangles + peeked mouse + warpRate*(now - lastCmdUs)`; the renderer subtracts the ref.
  `CL_PeekLookDelta` becomes `CL_PeekViewAngles`.
- LL-0 (uncapped): sample on the CPU at the end of the backend (removes cgame + front end + submit time, ~2-4 ms).
- LL-1 (paced, `r_frameWarpLatchSync` 1 = when paced, default; 0 never; 2 always): `gpuWait` waits on a fence placed
  after post-process (GL sync procs loaded with `SDL_GL_GetProcAddress` like `tr_gpuprof.c`), then until
  `deadline - latchLead` (P98 of sample->swap-return + 300 us), then samples. The pacer ring sample must be recorded
  when the fence signals, not after the deliberate wait: set `pacer.readyRecorded` so `Com_PresentWait` skips its
  finish and ring write for that frame (otherwise `Com_PaceLead` inflates every frame).
- `warpstats` latch lines: count, applied delta P50/P98 (deg), `cmd->sample` (`sampleUs - cl.lastCmdUs`) P50/P98 =
  camera latency removed, sample->swap-return P50/P98.
- Interfaces: refimport `qboolean (*WarpLatch)( void (*gpuWait)( void ), float *pitch, float *yaw )`; refexport
  `void (*WarpSetRef)( const vec3_t viewangles )`; `qboolean CL_WarpLatchView( float *pitch, float *yaw )`;
  `qboolean Com_WarpLatch(...)`; `void RB_WarpLatch( void )`.
- Go if: `cmd->sample` P50 >= 2 ms uncapped and >= 4 ms at a 237 cap, fps loss <= 3% uncapped, user's in-game check
  passes (HUD, ESC menu, console, cutscene, save/load, map change, alt-tab, screenshot; `r_aa` 4, 5 (MSAA), 8).
- Default-on question: only if it works independently of the frame pacer and mailbox/triple buffering (r_vsync 3);
  otherwise it stays a menu toggle.

Display note (user, 2026-10-24): the panel supports VRR (G-Sync/adaptive sync) in fullscreen only. Smooth-mode slot timing
therefore assumes VRR in fullscreen (slots at refresh minus ~3%, no oversampling) and treats windowed/borderless as the
no-VRR case (oversample ~0.8T).

## Architect deltas after AsyncTimewarp / OpenWarp review (2026-10-24)

- Both demos are single-thread "render occasionally, warp every loop"; they confirm our structure (FBO render, present as warp, UI after the warp, re-read input before each warp) but not single-context AP pacing. Cooperative checkpoints and the AP-0 timing spike stay the gate.
- 6-DoF step 11 becomes an OpenWarp-style mesh warp instead of per-pixel iteration:
  - Static grid at 1 vertex per 4x4 px (about 640x400); vertex shader reads captured depth, unprojects with the capture's inverse view-projection, reprojects with the warp's. Depth-tested into a depth attachment on `tr.warpOutFbo`; fragment shader only samples colour.
  - Raw depth plus the capture's own projection matrix (no linear-depth target). Downsample with min depth, also for the MSAA source.
  - Silhouette edges: min depth over the 3x3 cross/diagonals; if `z - min > r_frameWarpEdgeTol`, snap to near depth. Clamp z to 0.99 so sky stays put.
  - Gun: gun-mask vertices go to the dilated background depth; the gun is a second screen-locked pass using the existing mask.
  - Hole fill v1: stretched triangles. v2 (if smeared): flag stretched triangles and take the farthest-depth neighbour colour.
- Translation extrapolates from the last two captures (about one real frame of lag when acceleration changes). If visible: optional renderer import fed with cgame's predicted velocity; do not extend `refdef_t`.
- Go/no-go unchanged: `r_warpTestMove` synthetic `compare_shots`, warp GPU mark <= 0.5 ms. Oversample default ~1.25 only when no VRR (windowed/borderless); fullscreen VRR uses refresh-3%.
- VRR (fullscreen only): AP slots at ~0.97 x refresh, no oversampling; slot-completion jitter shows directly as display jitter (go/no-go: GPU-completion-to-slot error P98 < 0.5 ms). Windowed/borderless: oversample ~1.25. `r_frameWarpOversample` 0 = auto from fullscreen state, re-evaluated on `vid_restart`. The engine cannot detect whether KWin enabled VRR; the user checks the monitor's refresh readout. Open: does KWin keep VRR with `r_vsync 3` (mailbox) in fullscreen?

## Possible later changes (not needed now; user, 2026-10-25)

Late-latch with `r_frameWarpEdgeBlur 2` (default) looks fine at a 60 FPS cap when flicking fast; edges are unnoticeable. Parked, in case they are wanted later:
- Lower `r_frameWarpMaxDeg` (default 20) to about 8-10 as a low-FPS fallback: clips only extreme corrections (60 FPS cap P98 was 13 deg; uncapped P98 3.4 deg), costs a little of the latency gain on those frames.
- Adaptive overscan (`r_frameWarpOverscan`): render wider only when the measured correction is large; costs ~10% pixels (0.3-0.6 ms at 150 FPS) if always on, so never flat-on by default.
