# Memory profiler plan (RAM + VRAM, 2026-11-05)

Architect design, approved by the user incl. pak attribution. Goal: see WHERE memory goes (the totals come from
`scripts/bench.sh --memmon` / `scripts/memmon.sh`: ~650 MB RSS, ~1.5 GB process VRAM on the bench demo at 1920x1200).
Paths below are relative to `iortcw/SP/code` unless they start with `scripts/`, `profiling/` or `docs/`.

## Approach
A **census, not allocation hooks**. `rend2/tr_memprof.c` walks `tr.images[]`, `tr.fbos[]`, `tr.vaos[]` at sample points
and computes bytes analytically (no per-object GL calls: binding a texture to query it would corrupt rend2's `glState`
cache; the only GL call allowed is `glGetIntegerv(GL_GPU_MEMORY_INFO_*_NVX)`, same pattern as `GfxMemInfo_f`,
`rend2/tr_init.c` ~1374). `client/cl_memprof.c` breaks process RSS down from `/proc/self/smaps` and adds hunk stats,
`mallinfo2` and OpenAL buffer sizes. Both write `mem_*.csv` into `profiling/` (under the fs_homepath game dir, which
`bench.sh` already collects for `--profile`). `scripts/profile-report.py` adds a ranked "Memory" section and puts totals
next to memmon's nvidia-smi per-process VRAM (ground truth). Cost when off: one branch per frame and per load mark.

**Do not edit the canary files** (`docs/testing.md` "Safety rules"): `tr_backend.c`, `tr_fbo.c`, `tr_warp.c`,
`tr_postprocess.c`, `cl_scrn.c`, nor anything in the swap/present path. MSAA renderbuffer samples come from the cvar
`r_ext_framebuffer_multisample` (FBO_Init writes back the effective value, `tr_fbo.c` ~279).

Cvars: `com_memProfile` (CVAR_TEMP, default 0, not archived, not in any menu; read by engine and renderer),
`com_memProfileInterval` (ms, default 500, periodic timeline rate). Two timelines, one clock: renderer writes VRAM rows,
engine writes RAM rows, each stamped `CLOCK_REALTIME` ms; `memmon.sh` gets an `epoch` column; the report merges.

## Hunk attribution
Deltas at existing `Com_LoadProfileMark` stages (not HUNK_DEBUG): collision `sv:fs_restart`->`sv:cm_loadmap`
(`server/sv_init.c` ~833-837); game/AAS `sv:cm_loadmap`->`sv:gameprogs` (~861); renderer BSP `cg:world_begin`->
`cg:world_end` (`client/cl_cgame.c` ~591-593); cgame registration `cg:init_begin`->`cg:init_end` (~1028-1047).
Do not wrap `Z_Malloc` (plain `malloc`, `qcommon/common.c` ~888; `s_zoneTotal` is dead, so `meminfo` zone line is
meaningless). Use `mallinfo2` totals and present them as nested values, never added to the rollup.

## Bench-end dump
`CL_ReportBenchDemo` (`client/cl_main.c` ~891) calls the RAM dump and `Cbuf_ExecuteText(EXEC_NOW, "vramprof dump bench_end")`.
Fallback: the renderer dumps from `RE_Shutdown` before `FBO_Shutdown`/`R_DeleteTextures` (`tr_init.c` ~2159-2162) only if
no dump happened yet. Memory runs are separate from `r_gpuProfile` (gpuprof arrays inflate RSS; periodic samples add hitches).

## VRAM byte-size rules (`tr_memprof.c`; do NOT reuse `R_ImageList_f`: +50% mips (true ~+33%), ignores cubemap x6, R8/R32F/RG16F as 1 B/px, int overflow)
- 64-bit everywhere.
- Mips: if `flags & IMGFLAG_MIPMAP`, sum `MAX(1,w>>l)*MAX(1,h>>l)` until 1x1 from `uploadWidth/uploadHeight` (same loop as
  `R_CreateImageExt2` storage, `tr_image.c` ~2270-2290). Loader already clears the mipmap flag on compressed images with
  too few mips (~2686). Special case `tr.ssaoDepthImage`: `1 + tr.ssaoDepthMips` levels (~3057).
- `IMGFLAG_CUBEMAP` -> x6.
- Uncompressed B/texel: 4: RGBA8, SRGB8_ALPHA8, RGB8, SRGB8, RGB10_A2, R11F_G11F_B10F, RG16F, R32F, DEPTH24, DEPTH32/32F,
  DEPTH24_STENCIL8; 8: RGBA16F, RGBA16, RG32F; 16: RGBA32F; 2: RG8, LA8, R16F, DEPTH16, RGBA4, RGB5; 1: R8, L8.
- Compressed: `ceil(w/4)*ceil(h/4)` blocks/level; DXT1 and RGTC1 8 B/block; DXT3/5, RGTC2, BPTC 16 B (mirror
  `CalculateMipSize`, `tr_image.c` ~1968).
- Unknown format: `bytes=-1`, note `unknown_format`, counted in the summary. Never silently 0.
- Cinematic: `RE_UploadCinematic` re-specs `scratchImage` as RGB8 but leaves `internalFormat` stale (`tr_backend.c` ~1250);
  treat images named `*scratch` as 4 B/px.
- Renderbuffers: walk `tr.fbos[i]`: `colorBuffers[j]` use `colorFormat`; `depthBuffer`, `stencilBuffer`,
  `packedDepthStencilBuffer` use their own format fields (`tr_fbo.h` ~30-53); bytes = w*h*bpp*max(1,samples); samples
  nonzero only for `tr.renderFbo` with MSAA. Attached textures are already in `tr.images` (no double count). smaaBlend's
  edges DS buffer is attached directly (`tr_fbo.c` ~352-356), not double counted. Shadow FBOs' RGBA8 dummy colour buffers
  (FIXMEs at `tr_fbo.c` ~385, 397; flash FBO ~406) get category `rb_shadow_dummy_color`.
- Buffers: `vao->vertexesSize + vao->indexesSize` per `tr.vaos[i]`; categories by name: `VaoCache` -> `buf_vaocache`
  (fill from `VaoCache_GetStats`, `tr_vbo.c` ~1028), `tessVertexArray_VAO` -> `buf_tess`, `staticMD3Mesh_VAO` /
  `staticIQMMesh_VAO` -> `buf_models`, `warpMesh_VAO` -> `buf_warp`.
- Estimate rows (`kind=estimate`): loadscreen renderbuffer `ls.w*ls.h*4` (`tr_loadscreen.c` ~110, add a read-only getter);
  default framebuffer vidW*vidH*4*2 (+depth if the SDL context requests it, check `sdl_glimp.c`).

Image categories (column `category`, plus `map` = diffuse|normal|spec|-):
- Render-target pointer table (exact): `rt_scene` (render, renderDepth, world, worldDepth, upscale, dls, screenScratch,
  hdrDepth), `rt_ssao` (ssaoDepth, ao, screenSsao), `rt_smaa` (edges, blend, history A/B, velocity, area, search),
  `rt_bloom` (bloom[], quarter[]), `rt_sunrays`, `rt_shadow_sun` (sunShadowDepth[4], screenShadow), `rt_shadow_flash`,
  `rt_shadow_pshadow` (pshadowMaps[32], textureDepth, shadowCubemaps), `rt_warp` (warpDepth, warpMotion, warp, warpOut),
  `rt_cuberender`, `rt_tonemap` (levels images, textureScratch).
- Asset textures by name: `*cubeMap` -> `tex_cubemap_probes`; `*lightmap`/`_fatlightmap`/`lightmaps/` -> `tex_lightmap`;
  deluxe -> `tex_deluxemap`; `textures/` -> `tex_world`; `models/players/` -> `tex_players`; `models/weapons` ->
  `tex_weapons`; `models/` -> `tex_models`; `env/`/sky -> `tex_sky`; `gfx/ ui/ menu/ fonts/ sprites/` -> `tex_ui_fx`;
  `*scratch` -> `tex_cinematic`; other `*`/`_` -> `tex_builtin`; else `tex_other`.
- `map`: `IMGTYPE_NORMAL`/`NORMALHEIGHT` -> normal (height lives in the alpha); `_s` stem -> spec; else diffuse.
- `used_in_bench`: `image->frameUsed >= frame count at bench start` (`frameUsed` set in `GL_BindToTMU`, `tr_backend.c` ~59).

Expected at current settings (verify): `r_ext_compressed_textures 0` => every texture RGBA8+mips (2048^2 ~ 21 MB); sun
cascades 4x2048^2 depth 64 MB + 64 MB dummy colour; pshadow 32x512^2 depth 32 MB + 32 MB dummy colour (created
unconditionally, `tr_image.c` ~3066); VaoCache 60+16 MB (`tr_vbo.c` ~711-712); cubemap probes ~0.5 MB each at `r_cubemapSize 128`.

## Pak attribution (included)
- `renderercommon/tr_public.h`: add refimport `const char *(*FS_FileSourcePak)(const char *qpath);` at the END of `refimport_t`.
- `qcommon/files.c` + `qcommon.h`: `FS_FileSourcePak`, iterate `fs_searchpaths` like `FS_FileIsInPAK` (`files.c` ~2008); return
  the pak basename, `"dir"` for loose files, NULL if not found.
- `client/cl_main.c` `CL_InitRef` (~3794): wire it in.
- `rend2/tr_image.c`: `R_LoadImage` records the filename it actually resolved in a static (it can run on the offload
  worker while the main thread waits); `R_FindImageFileExt` reads that static on the main thread after the load and tags
  `image->memPak` (index into a renderer string table), only when `com_memProfile` is on. `rend2/tr_local.h`: `image_t` field.
  `com_memProfile` must be set before the map load. Changes the `refimport_t` layout: engine and renderer ship together
  (no `--game-only` build).

## Output schemas (fixed contract between chunks)
- `profiling/mem_vram_objects.csv`: `kind(texture|renderbuffer|buffer|estimate),category,map,pak,name,width,height,levels,faces,samples,format,bytes,used_in_bench,note`, sorted by bytes desc
- `profiling/mem_vram_categories.csv`: `category,count,bytes,mb,pct,bytes_used_in_bench`
- `profiling/mem_vram_timeline.csv`: `epoch_ms,t_ms,event,frame,bench,tex,rt,rb,buf,est,total,num_images,nvx_avail_kb,nvx_evict_count,nvx_evicted_kb`
- `profiling/mem_ram.csv`: `section,item,bytes,note`. Sections: `rollup` (rss, anon, file, shmem), `smaps_anon` (hunk, [heap],
  .so bss, anon_other, [stack]), `smaps_file` (basename, top 15), `smaps_dev` (/dev/nvidia*, memfd:), `hunk` (reserved,
  perm low/high, temp highwater), `hunk_phase`, `malloc` (in_use excluding hunk hblkhd, free_retained = fordblks, mmapped),
  `sound` (al_buffers, al_bytes), `derived` (unattributed_anon, profiler_overhead). `malloc` and `sound` rows have
  `note=nested` and are never added to the rollup.
- `profiling/mem_ram_timeline.csv`: `epoch_ms,t_ms,event,rss,anon,file,shmem,hunk_used,hunk_temp_hw,malloc_inuse,malloc_free,sound_bytes`
- `profiling/mem_meta.json`: resolution, GL renderer, NVX dedicated kb, bench start frame, cvars `r_ext_compressed_textures
  r_picmip r_cubemapSize r_shadowMapSize r_renderScale r_ext_framebuffer_multisample r_smaa r_ssao r_hdr r_sunShadows
  r_dlightMode com_hunkMegs`.
- Console commands: `vramprof [print|dump [why]]` (renderer), `memprof` (engine: RAM dump + `vramprof dump`).

## Steps
- **A (engine/client)**: `qcommon/common.c` (register cvars, `Hunk_GetMemStats()` exposing hunk_low/high, `s_hunkTotal`,
  `s_hunkData` base; at the top of `Com_LoadProfileMark` (~6431), before its early return and only off the worker thread,
  call `CL_MemProfEvent(stage)` under `#ifndef DEDICATED`), `qcommon/qcommon.h`, new `client/cl_memprof.c` (periodic sample
  from `/proc/self/smaps_rollup` + `mallinfo2` + hunk + sound, rate-limited; full `/proc/self/smaps` parse at dump only;
  timeline rows in a malloc'd array, its bytes reported as `profiler_overhead`; writes via `FS_WriteFile("profiling/...")`;
  `memprof` command; `#ifdef __linux__` and glibc >= 2.33 guard for `mallinfo2`), `client/snd_openal.c`
  `S_AL_MemStats(int*, long long*)` (sum `info.size` over `knownSfx` with `inMemory && !isDefault`; zeros if AL not up;
  declare in `snd_local.h`), `client/cl_main.c` (`CL_ReportBenchDemo` dump; `CL_Frame` periodic tick and rows at the edges of
  `cl_benchMeasuring`; `CL_InitRef` wiring of `FS_FileSourcePak`), `qcommon/files.c` + `qcommon.h` (`FS_FileSourcePak`),
  `renderercommon/tr_public.h` (refimport entry), `iortcw/SP/Makefile` (add `client/cl_memprof.o` to Q3OBJ ~1722 and
  `rend2/tr_memprof.o` to the rend2 list ~1844).
- **B (renderer)**: new `rend2/tr_memprof.c` (census, categories, top-N, timeline, writer, `vramprof` command, NVX sampling
  avail/eviction count/evicted), `tr_local.h` (declarations, `image_t.memPak`), `tr_init.c` (init + command registration next
  to `gpuprof` ~1970 and removal ~2142; `R_ShutdownMemProf()` fallback dump after `R_ShutdownGpuProf()` ~2159; event row in
  `RE_EndRegistration` ~2194), `tr_cmds.c` (one call `R_MemProfFrame()` in `RE_BeginFrame` after `tr.frameCount++` ~395:
  periodic rows, records bench-start frame on the 0->1 edge of `cl_benchMeasuring`), `tr_bsp.c` (event rows at start/end of
  `RE_LoadWorldMap` ~2961), `tr_model.c` (event row in `RE_BeginRegistration` ~2112), `tr_loadscreen.c` (read-only size
  getter), `tr_image.c` (pak tagging as above).
- **C (scripts)**: `scripts/memmon.sh` add `epoch` column; `scripts/bench.sh` add `--memprof` (sets `com_memProfile=1`,
  implies `--memmon`, clears `$HOME_CFG/profiling` like `--profile`, copies `profiling/mem_*` + the memmon csv into
  `$PROFILE_OUT/runK/` or `benchmarks/STAMP-LABEL-runK.mem/`; fix the stray indentation on the `--memmon` case line);
  `scripts/profile.sh` opt-in `--mem` pass (1 warm-up + 1 measured, gpuprof off) into `mem/`; `scripts/profile-report.py`
  writes session `mem_categories.csv` (median over measured runs) + merged `mem_timeline.csv` and a summary.md "Memory"
  section (VRAM accounted vs nvidia-smi per process, unaccounted remainder, eviction count; category ranking, top 25
  objects, bytes resident but unused in the bench window; RAM rollup decomposition, hunk by phase; load peak vs steady
  state vs bench end); `profiling/README.md` documents the files; `tools/rtcw-mcp/server.py` optional `memprof` flag.

## Risks
Formula vs driver (alignment, compression metadata, driver internals land in "unaccounted VRAM": report it); stale
`internalFormat` on out-of-band re-specification; periodic reads perturb FPS (never combine with `--profile` mode 1);
hunk is cleared on each map load (phase deltas are per load, timeline survives in malloc'd arrays); `bench.sh --set` writes
`seta` (archives `com_memProfile`; bench restores wolfconfig, MCP runs must too); Linux-only code behind `#ifdef`;
refimport layout change means a full build.

## Later
`memprof trim` experiment (`malloc_trim(0)` then re-sample) to quantify retained glibc heap after HD texture decodes;
possible exact GL verification via non-binding DSA getters.
