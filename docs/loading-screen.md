# Loading screen: never freeze

Goal: no present-to-present gap above 33 ms (30 FPS) while a map loads. All of it is internal engine config
(code defaults 0 = vanilla RTCW; the mod pins the values in `mod/codmod/codmod.cfg`). Code lives in the
`iortcw/` submodule (`SP/code/`).

## Problem and root cause

Vanilla redraws the loading screen only at the ~20 `CG_LoadingString` calls cgame makes during `CG_INIT`. Between
them come single blocks of 100 ms to 2 s (world load, HD textures, HD WAV decode, models). During
`SV_SpawnServer` the renderer and UI are shut down, so nothing can draw at all. The window looked frozen (first
present at ~1.1 s, 36 presents per load, max gap 1.7 s).

## Measuring: `com_loadProfile` and `scripts/load-test.sh`

`com_loadProfile 1` (2 adds stage marks) records every present during a local map load (`Com_PresentDone`) and
prints at the first `CA_ACTIVE` present:

```
LOADPROFILE <why> total=..ms frames=N maxgap=..ms@<stage> p95=..ms over33=N
LOADPROFILE_GAP 87ms @cl:end_registration t=4211 hint=textures/rock/roc_m01aa_nh
LOADPROFILE_MARK <ms> <stage>        (level 2)
```

A gap is labelled with the **last finished stage** (`Com_LoadProfileMark`), so the blocked work is what runs
*after* that mark. `hint=` is the asset most recently announced (`Com_LoadProfileHint`, set by the image, model and
sound loaders): the asset whose load blocked. The profiler state belongs to the main thread; `Mark`/`Hint` are no-ops
on the load worker.

`scripts/load-test.sh [--maps "escape1 escape2 village1"] [--level-change] [--profile-level N]` loads each map
off-screen (headless gamescope), restores `wolfconfig.cfg`, prints a summary and the gaps, exits 1 if any load has
`over33 > 0`. Raw logs: `benchmarks/load-<stamp>-<map>.log` (not committed).

Stage marks (level 2) cover: `sv:*` (savegame, fs_restart, cm_loadmap, gameprogs, settle, baseline, clients,
last_frame, end, gs_sent, frame_sim/frame_end for the first 3 server frames), `cl:*` (gs_parsed, gs_fs, gs_done,
dl_complete, sd_sound/sd_cgame/sd_ui/sd_ref and hunk_clear inside the memory flush, flush_begin/end, r_init, s_init,
s_beginreg, ui, cgame_begin, end_registration, touch_mem, hunk_usage, packets, first_snap) and `cg:*`.

## Phase 1: `CL_LoadingTick` (cl_scrn.c)

`com_loadingFps` (Hz). `CL_LoadingTick` does a full `SCR_UpdateScreen` redraw at most every `1000/com_loadingFps` ms.
Only call it at safe points: top-level cgame register syscalls (`cl_cgame.c`) and renderer loader loops
(`tr_bsp.c`). It is armed by the first `CG_UPDATESCREEN` and works only in the `CA_LOADING` window with the UI VM up.
**Never tick inside** shader parsing, image/file loads, sound buffer fills, or anything holding half-built renderer
state: a full redraw uses the renderer. Outside the window it falls back to the replay presenter.

## Phase 2a: replay presenter (rend2/tr_loadscreen.c)

`SCR_UpdateScreen` marks loading frames (`re.LoadingSnapshot(CL_LoadingFrameWanted())`); `RB_SwapBuffers` copies the
final back buffer into a renderbuffer + FBO kept in the file's own statics (not in `tr`, `glState`, `FBO_t`,
`image_t`), so it survives `RE_Shutdown(qfalse)` and the `tr` memset in `R_Init`. `RE_PresentLoadingSnapshot`
(`CL_LoadingReplayTick`, `R_LOADING_REPLAY()`, `ri.LoadingReplayTick`) blits it to the default framebuffer, draws an
animated spinner with scissored clears, `GLimp_SwapOnly()`s, and restores the GL bindings it touched. Raw `qgl` only:
no shaders, textures, VAOs, `tr.*`, Z/Hunk, FS or VM, so it is callable from anywhere: server spawn, `R_Init`, UI
init, `EndRegistration`, inside single image/sound loads. It skips when the drawable size changed since the
capture. `R_LoadScreenInvalidate()` runs when the GL context is destroyed (`GLimp_SetMode`); `R_LoadScreenShutdown()`
on real shutdown. `CL_LoadingReplayTick` is rate limited (shared limit with `CL_LoadingTick`) and a no-op unless
`com_loadingFps > 0` and `CL_LoadingStateOk()` (`CL_LoadingBegin` from `CL_MapLoading`, state `CA_CONNECTING`..`CA_PRIMED`,
`CL_LoadingEnd` at the first snapshot/disconnect/error).

## Phase 2b: offload with keepalive (client/cl_loadthread.c)

The gaps left after 2a are single CPU-bound calls the replay cannot be interleaved into. `Com_RunOffloaded(fn, arg)`
runs such a call on one persistent worker thread while the main thread waits on a semaphore (4 ms timeout) and calls
`CL_LoadingReplayTick()` between waits.

Conditions (otherwise `fn(arg)` is called directly, identical to the old behaviour): `com_loadingThread > 0`,
`com_loadingFps > 0`, a local load is on screen (`CL_LoadingFrameWanted()`), `re.PresentLoadingSnapshot` exists, the
caller is not already the worker and not already inside a job. DEDICATED builds: stub in `null/null_client.c`.

### Hand-off and thread rules

* **Synchronous**: only one thread runs engine code at a time. Z_Malloc, Hunk, FS, Cvar, Com_Printf, `va()` need no
  locking. `SDL_sem` post/wait provide the barriers. The worker is created lazily, joined in `CL_Shutdown`
  (`Com_OffloadShutdown`), never joined while parked.
* **Main-thread wait loop** (`Com_RunOffloaded`): `SDL_SemWaitTimeout`, then `CL_LoadingReplayTick`. The replay reads
  `com_loadingFps->integer`, `clc.state`, `loadingActive`, `Sys_Milliseconds`, then raw GL + `SDL_GL_SwapWindow` +
  `IN_PumpEvents` (`SDL_PumpEvents`) + `Com_PresentDone` (pacer statics, profiler gap record). No Z/Hunk allocation, no
  FS, no cvar writes, no Com_Printf, no `va()`.
* **Offloaded code must be CPU only**: no GL, no OpenAL, no VM calls, no screen updates.
* `CL_LoadingTick` / `CL_LoadingReplayTick` are no-ops on the worker (`Com_OffloadIsWorker()`, thread id check), so
  `R_LOADING_REPLAY()` calls inside offloaded loaders do nothing. `GLimp_SwapOnly` is only reachable through the replay.
* `Com_LoadProfileMark/Hint` are no-ops on the worker (profiler statics are read by the main thread's present hook).
* Shared statics (`curtime` in `Sys_Milliseconds`) are written by both threads but never at the same time except this
  benign int.

### Errors on the worker

`Com_Error` (and `Sys_Error`, as ERR_FATAL) on the worker would longjmp across threads. Both check
`Com_OffloadIsWorker()` first: they format the message, call `Com_OffloadWorkerError(code, msg)`, which stores
code + message in the worker's control block, posts the done semaphore and **parks the worker forever** (blocks on a
never-posted semaphore). The main thread sees the failed flag, copies the message, detaches the parked thread
(`SDL_DetachThread`, control block leaked on purpose), clears the worker pointer (a new one is created for the next
job) and calls `Com_Error(code, "%s", msg)` itself, so ERR_DROP/ERR_FATAL/ERR_DISCONNECT behave as before (longjmp to
`abortframe` on the main thread). Quit during a load cannot interleave with a running job (synchronous); the idle
worker is joined in `CL_Shutdown`, a parked one is simply abandoned to process exit. (A scripted `+quit` during a
load segfaulting independently is a separate known issue.)

### Offload targets

| Target | Where | CPU-only? | Result |
|---|---|---|---|
| HD/any texture read + decode | `tr_image.c` `R_LoadImageOffloaded` -> `R_LoadImage` (DDS/PNG/TGA/JPG/PCX/BMP loaders) | yes: FS read, Z alloc, decode; GL names are enums only | offloaded; `R_CreateImage` upload stays on main |
| Normal-map generation | same function | CPU math, but sits next to recursive `R_FindImageFile` + `R_CreateImage` | not offloaded |
| WAV/OGG decode | `snd_openal.c` `S_AL_BufferLoad` -> `S_CodecLoad` | yes: FS + codecs, hunk temp memory, no AL | offloaded; `alBufferData` stays on main |
| `CM_LoadMap` | `cm_load.c` (server `SV_SpawnServer` and client `CL_CM_LOADMAP`) | yes: FS, hunk, patch collision | offloaded (whole function; not for BSPC) |
| Model parse | `tr_model.c` `R_LoadMDC/MD3/MDS` | no: interleaved with `R_FindShader` (image upload) and VAO creation | skipped |
| FS_ReadFile above a size | | | not needed, skipped |
| AAS/botlib load | `BOTLIB_LOAD_MAP` syscall | botlib imports reach `VM_Call` (AICAST_*) and the syscall trampoline | skipped, not verified VM-free |

Cost: one hand-off is two semaphore operations (tens of microseconds); thousands of small images add up to tens
of ms of total load time at most.

## Phase 2c: the last gaps (instrumented, partly unmeasured)

Phase 2b left 5-6 gaps above 33 ms per map, the same on every map. Phase 2c could not be run by the agent (only the
orchestrator launches the game), so causes below are marked **measured** (from the 2b logs) or **static** (reasoned,
to be confirmed with the new marks).

| Gap | Where | Finding | Change |
|---|---|---|---|
| 35-69 ms @sv:fs_restart | `FS_Restart` (21 -> 69 ms) | **measured**: one block, nothing ticks inside; it reads the central directory of every pk3 (many HD/audio paks) | `CL_LoadingReplayTick()` after `FS_Shutdown`, after each `FS_LoadZipFile` in `FS_AddGameDirectory`, after `FS_Startup` (replay touches no FS state) |
| 34-54 ms @sv:gameprogs | `SV_InitGameProgs` = `G_InitGame` | **measured** as one block; no tick inside | `SV_LOADING_TICK()` (replay, `sv.state == SS_LOADING` only) in `SV_GameSystemCalls` for `G_FS_FOPEN_FILE`, `G_FS_FCLOSE_FILE`, `G_LINKENTITY`, `G_SET_BRUSH_MODEL`, `G_SET_CONFIGSTRING`, `BOTLIB_LOAD_MAP`. The AAS load itself stays one block (botlib imports reach the VM) |
| 145-204 ms @cl:sd_sound t~435-483 | between `sv:frame_end` (~315) and `cl:gs_parsed` (~483) | **measured** that the 168 ms are unmarked and are not the savegame (`sv:savegame` is at 21 ms) and not FS (marked separately); culprit **not yet known** | new budgeted marks `Com_LoadProfileFrameMark` (48 marks, armed by `sv:end`): `f:writecfg f:wait f:events f:cbuf f:sv f:events2 f:cbuf2 f:cl` per `Com_Frame`, and `gs:begin gs:clearstate gs:strings gs:sysinfo` in `CL_ParseGamestate`. `LP_MAXMARKS` 128 -> 192. Suspects in order: `S_StopAllSounds` inside `CL_ClearState` (AL calls, main thread only), `Com_WriteConfiguration`, the server frame tail, `Sys_Sleep` in the pacer |
| 92-145 ms @cg:world_begin t~1370-1412 | start of `RE_LoadWorldMap` | **measured**: the gap starts at `cg:world_begin`, not at sizzle.wav. The `hint=sizzle.wav` is stale (the last sound announced, the world load announces nothing). `alBufferData` is not the cause. The BSP `FS_ReadFile` (multi-MB pk3 inflate) runs before the first tick in `tr_bsp.c` | BSP read offloaded (`R_ReadBspJob` via `R_RUN_OFFLOADED`, then a replay), hints `bsp:read/entities/shaders/lightmaps/surfaces/nodes/lightgrid` so the stale hint is gone |
| 134-382 ms @cl:first_snap, at the End | first `CA_ACTIVE` frame | **static**: all GLSL programs are compiled eagerly in `R_Init` (with ticks), so the cost is the first real scene frame (driver-side lazy work, cold shadow/SSAO/FBO paths, `CL_FirstSnapshot` activeAction) | new mark `cl:first_frame_begin` right before the first `SCR_UpdateScreen` in `CA_ACTIVE`, so the End gap is attributed to the frame render. `com_loadingWarmup` **not implemented**: a dummy scene frame blocks the main thread as one block and cannot be split without touching the present path; measure the first-frame cost first (`gpuprof`, gap = `cl:first_frame_begin` -> End) |

`sizzle.wav` aside: `alBufferData` stays on the main thread (the context is made current globally with
`alcMakeContextCurrent`; uploading from the worker is not verified safe and no gap points at it).

### Reading the new marks

Run `scripts/load-test.sh` (profile level 2). `LOADPROFILE_MARK` now lists `f:*` and `gs:*` lines for the first six
frames after `sv:end`. The jump between two consecutive marks is the guilty step; a large `gs:clearstate` means
`S_StopAllSounds`, a large `f:sv` the server frame, `f:writecfg` the config write.

## Cvars

| Cvar | Code default | Pinned in | Meaning |
|---|---|---|---|
| `com_loadingFps` | 0 | `mod/codmod/codmod.cfg` = 50 | loading redraw/replay rate (Hz); 0 = vanilla |
| `com_loadingThread` | 0 | `mod/codmod/codmod.cfg` = 1 | offload CPU-only decodes to the worker; needs `com_loadingFps > 0` |
| `com_loadProfile` | 0 | (set on demand by `load-test.sh`) | 1 profile, 2 plus stage marks |

None are archived or in a menu. Rollback: `set com_loadingThread "0"` and/or `set com_loadingFps "0"` in
`codmod.cfg` (0 is byte-for-byte the old behaviour).

## Numbers

| Stage | presents / load | p95 gap | gaps > 33 ms |
|---|---|---|---|
| Baseline (vanilla) | 36 | max gap 1.7 s | 11-14 |
| Phase 1 tick | 115-128 | ~110 ms | ~35 |
| Phase 2a replay | 163-188 | 55-59 ms | 24-28 |
| Phase 2b offload | 214-253 (escape1 5251 ms / 253, escape2 4726 ms / 229, village1 4558 ms / 214) | 23 ms | 5-6 (escape1 5, escape2 6, village1 6) |
| Phase 2c | 231-256 (escape1 4876 ms / 246, escape2 5007 ms / 256, village1 4612 ms / 231) | 24-25 ms | 4-5 |

## Known unsplittable items

Anything CPU-bound that touches GL or shared renderer state stays on the main thread: GL texture upload (`R_CreateImage`),
`alBufferData`, model parse + VAO build, shader parsing, GLSL link, `re.Shutdown`/`CL_ShutdownAll` (GL deletes),
VM init, AAS load, the first server frames. Remaining unmarked stretches are now attributed by the extra marks above.

## What to test in game

Load-test run, then: a corrupt/missing asset during a load (error screen, no hang), quit during a load, `vid_restart`,
save/load, level change, HUD and ESC menu after the load (present path untouched, but verify).

## Later: first-frame warm-up (not done)

After 2c the biggest remaining gap on every map (all 32 load cleanly headless; 115-810 ms, usually 120-310 ms) is the first
gameplay frame, `cl:first_frame_begin`: the first full scene render (shadow maps, cubemaps, buffers on first use) is one
main-thread block. Idea: render one hidden scene frame (`com_loadingWarmup`, off by default) while the spinner still
animates, so the first real frame is cheap. It touches the render path, so it needs user verification and its own
measurement round. The idle connect-handshake frames now tick the replay (`CL_LoadingReplayTick` in `Com_Frame`).
