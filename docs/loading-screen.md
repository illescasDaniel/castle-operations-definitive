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
| Phase 2b offload | to be measured with `scripts/load-test.sh` | | |

## Known unsplittable items

Anything CPU-bound that touches GL or shared renderer state stays on the main thread: GL texture upload (`R_CreateImage`),
`alBufferData`, model parse + VAO build, shader parsing, GLSL link, `re.Shutdown`/`CL_ShutdownAll` (GL deletes),
VM init, AAS load, the first server frames. Remaining unmarked stretches are now attributed by the extra marks above.

## What to test in game

Load-test run, then: a corrupt/missing asset during a load (error screen, no hang), quit during a load, `vid_restart`,
save/load, level change, HUD and ESC menu after the load (present path untouched, but verify).
