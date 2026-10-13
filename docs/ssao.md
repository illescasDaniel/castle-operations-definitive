# SSAO (rend2): GTAO + depth-aware upsample

Engine-side only (`iortcw/SP/code/rend2/`). `r_ssao` (latched, 0/1, default 1 via `codmod_gfxdefaults.cfg`) still
turns the effect on; everything below is internal tuning with defaults in code.

## Pipeline (`RB_DrawSurfs` -> `RB_PostProcess`)

1. Depth prepass -> `hdrDepthImage` (full-res R32F) -> nearest downsample to `ssaoDepthImage` (half-res R32F; keeps
   the random AO taps in cache, no invented depths at edges).
2. `ssao_fp.glsl` at half-res, two variants chosen by `r_ssaoMode`:
   - `1` GTAO (default): slice-based horizon search + exact cosine-weighted arc (Jimenez 2016, structured like XeGTAO).
   - `0` hemisphere: 16-sample normal-oriented AO, kept as a fallback / A-B reference.
   Both rebuild view-space normals from depth, use interleaved gradient noise, take the radius in world units
   (FOV independent) and skip view model (depth <= 0.3, drawn with `glDepthRange(0,0.3)`) and sky pixels.
3. `depthblur_fp.glsl` H + V at half-res; depth tolerance is relative (3% of distance + 1.5 units).
4. `ssaoup_fp.glsl`: depth-aware bilateral upsample into the scene (multiply blend), fades to 1 between 1500 and 4000
   units, 1 on sky/view model.

## Cvars (not archived, not menu-exposed)

| cvar | default | meaning |
|---|---|---|
| `r_ssaoMode` | 1 | 0 hemisphere, 1 GTAO |
| `r_ssaoRadius` | 40 | world units |
| `r_ssaoStrength` | 1 | GTAO: visibility^(2*strength); hemisphere: linear gain |
| `r_ssaoSlices` / `r_ssaoSteps` | 2 / 4 | GTAO slices per pixel / steps per side |
| `r_ssaoSamples` | 16 | hemisphere sample count |

## Cost (RTX 4070 Laptop, 2561x1601, SMAA 3, bench demo, uncapped, median of 3)

| config | FPS |
|---|---|
| SSAO off | 255 |
| GTAO 2x4 (default) | 192 |
| GTAO 2x6 | 183 |
| GTAO 1x2 / 4x12 | 209 / 111 |

Findings: cost is texture-fetch bound (wide near-field radii miss the cache); half-res depth gave +7%, capping the
screen radius helps more. Depth mips (XeGTAO style) would be the next step if more speed is needed.

## In-game setting (`r_ao`)

GRAPHICS > Ambient Occlusion sets `r_ao` (archived, default 2, reset in `codmod_binds.cfg`). `R_ApplyAO()` (called from
`RE_BeginFrame` when `r_ao` changes) derives `r_ssao`/`r_ssaoMode`/`r_ssaoSlices`/`r_ssaoSteps`; changes apply live with
no restart (SSAO images are always allocated; the depth copy only runs when AO or shadow blur is on).

| r_ao | Mode |
|---|---|
| 0 | Off |
| 1 | SSAO, hemisphere (16 samples) |
| 2 | GTAO Low (1 slice x 2 steps), default |
| 3 | GTAO Medium (2 x 4) |
| 4 | GTAO High (2 x 6, strength 0.8) |
