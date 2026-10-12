# SMAA anti-aliasing (replaces MSAA 2x as default) — plan

Status: **done** (implemented, benchmarked +18% vs MSAA 2x, user-tested in game: HUD/menus fine) (2026-10-12). SMAA code is by Jimenez et al. (MIT), see [credits.md](credits.md). Engine work in `iortcw/` (branch `codmod`), rend2 only.

## Goal

Add SMAA 1x as a rend2 post-process pass, make it the codmod default, and set MSAA off by default.
Keep MSAA available in the menu.

Why: `docs/performance.md` Findings show MSAA 2x costs **28%** (165 → 211 FPS with it off, 2561x1601,
RTX 4070 Laptop). SMAA 1x High typically costs ~0.3–0.6 ms at that resolution, so expect about
**190–200 FPS** (+15–20% vs today). This is an estimate; step 8 measures it. Quality: SMAA catches edges
MSAA 2x misses (alpha-tested fences, grates and foliage, which MSAA without alpha-to-coverage does not
smooth, plus some shading aliasing). On geometric edges it is about as good as MSAA 2x and not as
good as 4x. It does not fix sub-pixel shimmer on thin wires (MSAA 2x mostly doesn't either).

## Design

**Where the pass runs:** inside `RB_PostProcess` (`rend2/tr_backend.c`), right after the
tonemap/exposure block and **before** sun rays, bokeh and all 2D. Reasons:

- Input must be display-referred LDR. After `RB_ToneMap` the color is clamped to [0,1] in the gamma-space
  that RTCW textures use, which is what SMAA's luma edge detection expects.
- 2D (HUD, menus, console, scope overlays) is drawn *after* post-process, so it stays sharp and is never
  smoothed by mistake.
- **`RB_SwapBuffers` and the present path stay untouched** (safety rule 1 in `docs/testing.md`). The pass
  writes its result back into `srcFbo` (same pattern the tonemap uses via `screenScratchFbo`), so the
  frame flows on exactly as it does now.

**Passes (standard SMAA 1x, from iryoku/smaa, MIT):**

| Pass | Reads | Writes |
|---|---|---|
| 1. Luma edge detection | `srcFbo` color (`tr.renderImage`) | `tr.smaaEdgesFbo` (RG8, cleared to 0 in `dstBox`) |
| 2. Blend weights | edges + `AreaTex` (160x560 RG8) + `SearchTex` (64x16 R8) | `tr.smaaBlendFbo` (RGBA8) |
| 3. Neighborhood blending | `srcFbo` color + blend weights | `tr.screenScratchFbo`, then `FBO_FastBlit` back to `srcFbo` |

Viewport: work in `dstBox` (viewport/scissor) with full-screen `SMAA_RT_METRICS`, so sub-views and
cinematic letterboxing behave the same way as the other post passes. With MSAA also on, `srcFbo` is
`msaaResolveFbo` (its color is also `tr.renderImage`), so SMAA runs on the resolved image. That combination
is allowed, just not the default.

**Stencil early-out:** skip for v1 (pass 2 already discards fast on edge-free pixels). Only add it if step 8
shows pass 2 is costly.

## Steps

### 0. Baseline
`scripts/bench.sh` 3 runs each: current defaults (MSAA 2) and `--set r_ext_framebuffer_multisample 0`.
Note GPU idle (earlier noisy numbers came from background GPU work). Take reference screenshots at
2–3 fixed spots: a fence or grate, foliage, long diagonal geometry, the weapon viewmodel.

### 1. Vendor SMAA
- `rend2/glsl/smaa_lib.glsl` = upstream `SMAA.hlsl`, unmodified, with its MIT header (stringified by the
  existing `$(B)/rend2/glsl/%.c` Makefile rule).
- `rend2/smaa_tex.h` = upstream `AreaTex.h` + `SearchTex.h` byte arrays (MIT headers kept).
- Add the new `glsl/*.o` objects to the rend2 object list in `SP/Makefile` (next to `bokeh_fp.o`, ~line 1896).
  The MP renderer is not touched.

### 2. Images and FBOs (`tr_image.c`, `tr_fbo.c`, `tr_local.h`)
- `R_CreateBuiltinImages`: `tr.smaaAreaImage`, `tr.smaaSearchImage` (from the arrays, `IMGFLAG_NO_COMPRESSION |
  IMGFLAG_CLAMPTOEDGE`, linear for area, nearest for search), `tr.smaaEdgesImage` (RG8),
  `tr.smaaBlendImage` (RGBA8), full render size.
- `FBO_Init`: `tr.smaaEdgesFbo`, `tr.smaaBlendFbo`, created next to `screenScratchFbo` (so `vid_restart` and
  resolution changes rebuild them through the same path).
- Edge case: with `r_hdr 0` **and** MSAA off, rend2 renders straight to the backbuffer (`tr.renderFbo == NULL`)
  and has no post-process. Codmod pins `r_hdr 1`, so v1 just leaves SMAA inactive there and prints one
  console warning. It does not change the `renderFbo` creation logic (`tr_fbo.c` is on the safety list).

### 3. Shaders (`tr_glsl.c`, `tr_local.h`)
- 3 programs: `smaa_edge_{vp,fp}`, `smaa_weights_{vp,fp}`, `smaa_blend_{vp,fp}`. Each is a thin wrapper that
  sets `#define SMAA_GLSL_3`, `SMAA_RT_METRICS u_SmaaRtMetrics`, `SMAA_INCLUDE_VS`/`_PS`, then includes the
  `smaa_lib` string (prepended through the `extra` header argument of `GLSL_InitGPUShader`). Uses rend2's
  `attr_Position`/`attr_TexCoord0` and `u_ModelViewProjectionMatrix` like `tonemap_vp.glsl`.
- Presets: build edge + weights for LOW/MEDIUM/HIGH/ULTRA at init (8 small programs; the blend pass doesn't
  depend on the preset). Then `r_smaa` switches live without recompiling.
- New uniform `UNIFORM_SMAARTMETRICS` (vec4). Samplers: reuse existing TB_ slots (`TB_COLORMAP`, `TB_LEVELSMAP`,
  …) the way `RB_ToneMap` binds `u_LevelsMap`.
- Requires GLSL ≥ 1.30 (`textureLod`, offsets). On the `#version 120` path: skip compiling and force SMAA off
  with a console note.
- Iterate with `r_externalGLSL 1` (loads `glsl/*.glsl` from disk) so shader tweaks don't need a rebuild.

### 4. Backend pass (`tr_backend.c`)
- New `RB_SMAA(FBO_t *src, ivec4_t box)` called in `RB_PostProcess` right after the tonemap/`r_cameraExposure`
  block, guarded by `r_smaa->integer && tr.smaaEdgesFbo && srcFbo`.
- Pass 1: bind edges FBO, clear in box, `FBO_Blit` with the edge shader. Pass 2: blend FBO, clear, bind area/search
  to their TMUs, draw. Pass 3: neighborhood blend into `screenScratchFbo`, then `FBO_FastBlit` back into `srcFbo`.
- `r_smaaDebug 1/2` shows the edges or weights buffer instead of the result. It's a debug cvar, not archived.
- Nothing in `RB_SwapBuffers`, `RB_EndFrame` clears or `tr_cmds.c` changes.

### 5. Cvars (`tr_init.c`)
- `r_smaa` 0 off, 1 low, 2 medium, 3 high, 4 ultra. `CVAR_ARCHIVE`, **not latched**, range-checked 0–4. Default
  in the engine stays `0` (stock behavior); codmod sets 3.
- `r_smaaDebug` 0–2, cheat/dev only.
- Add both to `iortcw/rend2-cvars.txt`.

### 6. Codmod defaults
- `mod/codmod/codmod.cfg`: `seta r_ext_framebuffer_multisample "0"`, `seta r_smaa "3"`, and update the comment.
- `scripts/run.sh`: `+set r_ext_framebuffer_multisample 0` (was 2). Note: `run.sh` and `codmod.cfg` re-apply
  these every launch, so a menu MSAA choice doesn't survive a restart today. Keep that behavior for v1 (same as
  every other pinned rend2 default) and mention it to the user. **No edits to `wolfconfig.cfg`**; the
  latch/`seta` path covers existing installs.
- `scripts/bench.sh`: add `r_smaa` to the run header next to res/MSAA.

### 7. Menus (`codmod_menus.pk3`)
- `mod/codmod/ui/options.menu` and `ingame_options.menu` (GRAPHICS): new row `SMAA:` on `r_smaa` with
  `cvarFloatList { "Off" 0 "Low" 1 "Medium" 2 "High" 3 "Ultra" 4 }` above the existing `MSAA:` row. Hint
  strip text: "SMAA: fast edge smoothing (recommended). MSAA: slower, needs restart." MSAA row unchanged.
- Repack with `scripts/install.sh`. Check pad focus order still works (spatial nav picks up the new row).

### 8. Verify
- Bench 3 runs each: MSAA 2 (old default), MSAA 0 + SMAA 3, MSAA 0 + SMAA 4, MSAA 0 + SMAA 0. Record in
  `docs/performance.md`. Target: SMAA 3 ≥ +12% avg FPS over MSAA 2.
- A/B screenshots at the step 0 spots, plus `r_smaaDebug 1` to confirm edges are found on fences and the viewmodel.
- `vid_restart`, resolution change, in-place fullscreen toggle (under `game_run.sh`): no GL errors, no smear.
- Binoculars/sniper scope, cutscene letterbox, menu with a map running behind it (bokeh blur), loading a save.
- **User canary (safety rule 1):** HUD visible and ESC pause menu visible in a real map, with SMAA on **and**
  with MSAA 2 + SMAA on.

### 9. Wrap-up
- Update `docs/performance.md`, `memory/progress.md`,
  `memory/decisions.md` (+ jevmem fact): "SMAA 1x High replaces MSAA 2x as default; reasons + numbers".

## Alternatives considered

- **FXAA:** cheaper, but blurs textures and text-like detail (HD textures would lose sharpness). Rejected.
- **SMAA T2x / TAA:** better on shimmer but needs camera jitter + per-pixel motion vectors; rend2 has neither.
  Out of scope.
- **SMAA S2x (MSAA 2x + SMAA):** works for free with this design (enable both). Offered as a menu combo, not
  as the default, because it brings back most of the MSAA cost.

## Risks

- Present-path regressions (the HUD incident): mitigated by keeping the pass inside `RB_PostProcess`
  before 2D and leaving `RB_SwapBuffers` alone; canary passed (user playtest, 2026-10-12).
- `r_hdr 0` + MSAA off: no FBO, so SMAA is inactive (warned, documented).
- Portal/camera views: `RB_PostProcess` runs only for world views; check that portal scenes don't run SMAA twice
  on the main view (cheap even if they do).

## Update: single `r_aa` setting (2026-10-12)

The menu has one **Anti-Aliasing** row on the new cvar `r_aa`: 0 Off, 1-4 SMAA Low/Medium/High/Ultra, 5-7 MSAA 2x/4x/8x.
SMAA levels are quality presets (edge threshold, search steps, diagonal/corner detection), all 1 sample per pixel, so
they are not labelled x1/x2. `R_ApplyAA` (`tr_init.c`) translates `r_aa` into `r_smaa` (live) and
`r_ext_framebuffer_multisample` (latched, needs Apply/vid_restart); it runs at init and from `RE_BeginFrame` when
`r_aa` changes. `r_aa -1` (engine default) leaves the two cvars alone. Engine default is `r_aa 3`; the choice persists in wolfconfig (archived) and `codmod_binds.cfg` (menu RESET SETTINGS, `--reset-binds`/`--reset-settings`, first launch) resets it together with `com_maxfps`, `com_maxfpsMode` and `r_vsync`. SMAA works without MSAA
as long as the render-FBO path is on (`r_hdr 1`, pinned by codmod.cfg).
