# SMAA on moving objects — plan

Status: **plan only** (2026-10-21), not implemented. Builds on [smaa.md](smaa.md) (SMAA 1x, `r_aa 3` default).

## Problem

Animated objects shimmer and their edges crawl while they move, more than static geometry does. Example: the
two hanging cages on escape1 (`props_decoration`, `models/mapobjects/torture/cage1.mdc` / `cage2.mdc`, 67-frame
looping swing, `spawnflags 100`, around origin `1646 160 -676`). Same issue on doors and movers, swinging lamps, the
viewmodel and enemies.

## What the code shows

- **The cages are real thin geometry.** They are opaque, with no shader script, so the implicit shader uses
  `ametal_m03dm.jpg` with no alpha test. Alpha-to-coverage would not help. The bars and chains are about 1-3 px
  wide at normal distances.
- **The animation is already smooth.** The server steps `s.frame` every 50 ms (`props_decoration_animate`,
  `g_props.c:3149`). `CG_General` lerps it (`oldframe = frame - 1`, `backlerp = 1 - cg.frameInterpolation`), and
  rend2 blends the two MDC frames on the GPU (`u_VertexLerp`). The crawling does not come from a choppy animation.
- **SMAA 1x is purely spatial**, so each frame is anti-aliased on its own. On a moving thin edge the staircase
  pattern changes every frame, and so does what SMAA rebuilds. Sub-pixel bars come and go between frames. A static
  scene looks clean because the same pattern repeats every frame. Motion makes the aliasing visible. Only more
  samples fix this: MSAA, or temporal accumulation (T2x/TAA).
- **Luma edge detection misses dark-on-dark edges.** The High preset threshold is 0.1 in gamma luma. Escape1's
  dungeon is dark, so the rusty bars against dark stone may fall under the threshold and get no AA at all. This is
  likely part of what the user sees, and it is cheap to fix.
- Useful facts for the temporal work:
  - `refEntity_t.entityNum` exists, so the previous frame's transform can be kept per entity.
  - The depth prepass (`tr_backend.c:1476`) already draws every opaque surface, which makes it the natural place
    to write motion vectors.
  - MD3/MDC vertex animation runs on the GPU (two frames plus a lerp value).
  - MDS characters are skinned on the CPU (`RB_SurfaceAnim`, `tr_animation.c`), which makes their per-vertex
    motion harder.
  - The vendored `smaa_lib.glsl` already has `SMAA_PREDICATION`, `SMAA_REPROJECTION`, `subsampleIndices` and
    `SMAAResolvePS`.

## Phase 0 result (user screenshots, 2026-10-21)

The user took screenshots at the cage with and without `r_smaaDebug 1`.
- The outer silhouettes are found: the near-vertical bars show long, unbroken red lines.
- Some edges are broken into dashes: the near-horizontal diagonals (green) and the bar sides with low contrast.
- The edge map is full of speckle from texture and lighting detail, on the stone wall on the right and on the bar
  faces. SMAA's pattern search stops where these false edges cross a real one, so long diagonals get the wrong
  pattern length and blend in short, uneven steps. That is the "imperfect diagonals", and it also softens the HD
  textures.
- The cage's shadow on the wall has no depth edge. Its stair steps come from the shadow-map texels and are several
  pixels wide, which SMAA cannot rebuild. That is shadow filtering, not anti-aliasing.
- The thin gold specular lines on the bar edges are specular aliasing: they shimmer when the cage swings, and no
  post-process AA fixes that.

So Phase 1 should use the library's **default** `SMAA_PREDICATION_SCALE` (2). It raises the threshold away from
depth edges, which removes the speckle, and lowers it on depth edges, which closes the dashes. Phase 1b
(specular AA) and the shadow item cover the rest.

## Plan (phase-gated, user checks in game after each phase)

### Phase 0 — Diagnose (no code changes)

Go to the escape1 cages (`devmap escape1`, `setviewpos` near `1540 160 -640`) and compare:
1. `r_smaaDebug 1`: are the bar edges detected at all while the cage swings? If many are missing, Phase 1 is the
   main fix.
2. `r_aa 3` (SMAA High), `r_aa 4` (Ultra, threshold 0.05), `r_aa 6` (MSAA 4x): which one the user finds
   acceptable, using short recordings or eyeballing.
3. If Ultra already looks much better, the cause is missed edges (Phase 1). If only MSAA 4x looks good, the cause
   is sub-pixel crawl (Phases 2-3).

### Phase 1 — Depth-predicated edge detection (small, ~0.05 ms)

Turn on `SMAA_PREDICATION` in the edge pass. Where the depth buffer shows a geometric edge, the luma threshold is
lowered, so dark bars against a far wall get AA even with little luma contrast.
- Predication input: linear depth from `tr.hdrDepthFbo`, which is filled after the prepass only when
  `r_ssao || r_shadowBlur`. Make it available whenever SMAA predication is on.
- Change: compile flag in the `smaa_edge_*` programs (`tr_glsl.c:1375`), bind the depth to a free TB slot in
  `RB_SMAA`.
- Tune `SMAA_PREDICATION_SCALE`. The library default of 2 *raises* the threshold on edges that are only in the
  texture, so texture detail would get less AA. Start at 1.0 with strength 0.4 and A/B on HD textures.
- Cvar `r_smaaPredication` (internal, pinned in `codmod.cfg`). Not a menu row.

**Implemented (2026-10-21).** `SMAA_PREDICATION` is on in the edge shaders (`tr_glsl.c` SMAA header, `smaa_edge_fp.glsl`). Input is
`tr.hdrDepthImage` (R32F copy of the main-view depth, same size as the SMAA targets, bound to `TB_LEVELSMAP`). The depth copy
in `tr_backend.c` now also runs when `r_smaa && r_smaaPredication`. The edge shader linearizes it and takes `-log2(z/zFar)`
through a small hook in the vendored lib (`SMAA_PREDICATION_FETCH`), so the threshold is a relative depth jump:
`r_smaaPredThreshold` 0.06 (about 4%), `r_smaaPredScale` 2.0, `r_smaaPredStrength` 0.4 (library defaults; the three are
non-archived tuning cvars passed through `u_ViewInfo`). `r_smaaPredication` 0/1 (engine default 0, pinned 1 in `codmod.cfg`) is
live: "off" is scale 1 / strength 0 on a white dummy texture, giving the plain threshold, so there is still one edge program
per preset. Predication also stays off without a depth prepass or for no-world frames. Checked on the bench demo with
`r_smaaDebug 1`: texture/wall speckle is gone and silhouettes remain (interior armour edges of the knight thin out, as intended).
Cost not measured.

### Phase 1b — Specular anti-aliasing (small)

In `lightall_fp.glsl`, widen roughness where the normal changes quickly across a pixel (Kaplanyan/Tokuyoshi
geometric specular AA from `dFdx`/`dFdy` of the normal, or Toksvig from normal-map mip length). This stops
one-pixel-wide highlights on thin metal from flickering while it moves. Internal cvar `r_specularAA`.

**Implemented (2026-10-21, uncommitted).** Kaplanyan 2016 / Tokuyoshi-Kaplanyan 2019 in `lightall_fp.glsl`, right after
the final normal `N` is normalized (uniform flow, before any branch): `var = dot(dFdx(N)) + dot(dFdy(N))` (squared
lengths); `alpha2 = roughness^4 + min(0.5 * r_specularAA * var, 0.18)` (SIGMA2 0.25 and a 2x factor, KAPPA 0.18, all at
strength 1), then `specRoughness = alpha2^(1/4)` because `CalcSpecular` squares roughness itself. `specRoughness` feeds
the direct deluxe/light-grid specular, the dynamic-light (flashlight) specular, the primary-light specular, and the
cubemap mip + `EnvironmentBRDF`; diffuse keeps the original roughness. Cvar `r_specularAA` (float, engine default 0,
live): passed in the spare `u_AoParams.w` (set in the lightall stage block and `SetDlightShadowMask` in `tr_shade.c`);
0 skips the math. The mod pins it to 1 in `codmod.cfg`. No menu row. Smoke test (`shots.sh`, bench demo): 1-2% of
pixels differ, on and off; no GLSL errors.

### Shadow edges (separate item, not AA)

The stair steps on the cage's shadow come from shadow-map texels. Options: a wider PCF kernel for `r_shadowFilter 2`,
or a tighter sun cascade split. Look at this separately if the user wants.

### Phase 2 — "SMAA + MSAA 2x" menu option (tiny; costs about what MSAA 2x does)

`R_ApplyAA` (`tr_init.c:1366`) only offers SMAA *or* MSAA. Add `r_aa 8` = SMAA High on the MSAA 2x-resolved
image. This is not the real S2x, which runs SMAA per sample with `subsampleIndices`, but it is the existing
pipeline running both. Each pixel then has two coverage samples on thin bars, which is the cheapest real fix for
sub-pixel crawl. Menu row value "SMAA + MSAA 2x". It stays opt-in and is not the default (about -20-28% FPS).

### Phase 3 — SMAA T2x (large, the real fix)

Alternate a sub-pixel camera jitter each frame and blend with the reprojected previous frame. Each pixel then gets
two samples over time at about the cost of SMAA 1x plus a velocity buffer. It only works on moving objects if they
have correct motion vectors. Without them their history is rejected and they fall back to today's 1x look.

**Staging (decided after the screenshots).** Phase 3 can ship in two steps:
- **3-cam (~1 session):** jitter, resolve and history, with motion worked out from depth and the previous frame's
  `viewProj` inside the resolve pass. No velocity buffer and no prepass changes. The whole static world gets
  2-sample temporal AA while the player moves or turns, which is when most crawling shows. Moving objects get wrong motion, so
  the clamp mostly rejects their history and they look about the same as today. Check them for faint ghosting.
- **3-obj (~1-2 sessions):** the velocity buffer below. This is what makes the cages, doors and the viewmodel
  benefit.

**3a. Velocity buffer**
- New `tr.velocityImage` (RG16F, render size) attached as a second color target of `renderFbo` (and of
  `msaaResolveFbo`'s path when MSAA is on). It is written only during the depth prepass. The prepass keeps the
  depth-only color mask for attachment 0 and enables attachment 1. The prepass shader variants (generic/lightall
  depth fill) get a `USE_VELOCITY` define: `velocity = ndc_cur.xy - ndc_prev.xy` (jitter removed).
- **Camera:** previous `viewProj` kept in `tr` (main view only; portals, mirrors and shadow views get none).
- **Rigid entities (brush movers, misc/props models, doors, cages' entity transform):** `prevModelMatrix[entityNum]`
  plus the frame count it was written in. If it is missing or stale (new entity, teleport, a jump bigger than a
  threshold), use the current matrix, which means zero object motion.
- **MD3/MDC vertex animation (cages, lamps, flags):** the shader already has both frames' positions. Within one
  frame pair the vertex velocity is constant, `(P_frame - P_oldframe) / frameTime`, so
  `prevPos = curPos - (P_frame - P_oldframe) * (lerp_cur - lerp_prev)`. Keep `prevBacklerp[entityNum]`. When the
  pair changed since last frame, extrapolate with the per-frame lerp delta. This needs no extra vertex attributes,
  only one uniform.
- **Viewmodel (`RF_DEPTHHACK` / `RF_FIRST_PERSON`):** it moves with the camera, so its motion is in view space.
  Keep its previous matrix in view space, or else it smears on every mouse turn. Same for the ADS model.
- **MDS characters (CPU skinning):** v1 uses entity-transform motion only. Limb motion is left to the history
  clamp, below. Optional Phase 4: keep last frame's skinned positions per entity/surface and upload them as a
  second position stream.
- **Sky / far plane:** camera rotation only (w = 0 reprojection).
- **Translucents (particles, smoke, glass, fire):** not in the prepass, so they have no velocity and use the
  background's motion. The clamp handles them.

**3b. Jitter**
- Offset the main-view projection matrix by ±0.25 px in the SMAA T2x pattern
  (`subsampleIndices` (1,1,1,0) / (2,2,2,0)), alternating per rendered frame.
- Never jitter: 2D/HUD (drawn after post-process anyway), shadow/sun/flashlight views, cubemap renders,
  portals/cameras, menus with no world, and paused or `cl_paused` frames with no new frame.

**3c. Temporal resolve**
- After `RB_SMAA` writes the 1x result, `SMAAResolvePS` (with `SMAA_REPROJECTION 1`) blends it with
  `tr.smaaHistoryImage` (RGBA8 LDR, previous resolved frame) at the reprojected position. Then the result is
  copied into history.
- Add a **3x3 neighborhood clamp** (YCoCg min/max) on the history sample on top of SMAA's velocity weighting.
  The reference resolve alone ghosts on disocclusion and on anything without correct velocity (MDS limbs,
  particles).
- Same place in `RB_PostProcess` as today: after tonemap, before sun rays, bokeh, bloom and 2D. **`RB_SwapBuffers`
  and the present path stay untouched** (safety rule 1).
- Reset history (resolve passes the current frame through) on: map load, `vid_restart`, resolution or `r_aa`
  change, cutscene camera cuts, large view jumps (teleport, death cam, save load), and the first frame after
  pause.

**3d. Settings**
- New `r_aa` values: SMAA T2x (High). Decide with the user whether T2x becomes the default after A/B, since it adds a
  slight softness in motion. Internal cvars: `r_smaaTemporal`, `r_smaaJitter` (debug), `r_smaaDebug 3` (velocity
  view).

**3e. Cost estimate (to measure on the bench demo):** the velocity MRT write in the prepass is ~0.2-0.4 ms at
2561x1601, the resolve and history copy ~0.1-0.15 ms. Expect about 5-8% FPS below SMAA 1x High, still well above
MSAA 2x.

**3f. Risks**
- Ghosting or smear on fast motion or missing velocities: clamp, velocity weighting, and `r_smaaDebug 3` to find
  objects with no motion vectors.
- Jitter shimmer at low frame rates (30 FPS): the resolve averages it out on static views. Check with
  `com_maxfps 30`.
- Shader variant count grows (depth-fill × vertex/bone animation × velocity). Velocity is only compiled into the
  depth-fill variants.
- GTAO noise becomes temporally jittered (probably fine or even better). Bloom and auto-exposure are unaffected
  (they run after the resolve, or on its result).
- Must check: binoculars/scope zoom (FOV change → reset or accept one blurred frame), cutscene letterbox, mirror/
  portal surfaces, the `vid_restart` soft path, and MSAA + T2x (disallow it at first).

### Phase 4 (optional) — MDS character motion vectors

Per-entity cache of last frame's skinned vertex positions, uploaded as a second position stream. This gives
enemies proper T2x instead of the clamped fallback. Do it only if Phase 3 shows enemies still crawling.

## Recommendation

1. Phase 0 (15 minutes in game) to see which problem dominates.
2. Phase 1 and Phase 2 are each well under a day and low risk. Phase 1 likely helps the dark escape1 cages right
   away. Phase 2 gives a quality option for users with GPU headroom.
3. Phase 3 is the real fix for motion crawl but a multi-day change (prepass MRT, per-entity history, jitter,
   resolve). Start it only if Phases 1-2 are not enough.

## Alternatives considered

- **Generic TAA (no SMAA):** gives more samples over time, but is blurrier and ghosts more. The HD textures would
  lose sharpness, which is the same reason FXAA was rejected. T2x keeps SMAA's sharp spatial pass and uses only 2
  frames.
- **Real SMAA S2x / 4x** (per-sample SMAA on MSAA 2x): better than Phase 2 but needs MSAA sample-pattern-aware
  passes and SMAA per sample. Revisit only after Phase 3.
- **Higher internal resolution (SSAA / render scale):** fixes everything but costs far too much at 2561x1601.
- **Thicker LOD geometry for thin props:** asset work for each prop, does not scale.
