# Stable sun shadows

Cascaded sun shadows (`r_forceSun 1`, `r_sunShadows 1`, 3 cascades + a level-wide 4th) used to swim when the
camera turned or moved. Fix lives in `iortcw/SP/code/rend2` behind the latched bitmask `r_sunShadowStable`
(pinned `7` in `mod/codmod/codmod.cfg`; `0` = vanilla rend2, for A/B). Change needs `vid_restart`/relaunch.

| Bit | What | Where |
|---|---|---|
| 1 | Stable cascades 0-2: light view has fixed world-up axes, is anchored at the world origin (not the camera), and each cascade is a square of the slice's bounding-sphere diameter, snapped to whole texels. Size no longer changes with camera rotation, so the map only shifts by exact texels. | `tr_main.c` `R_RenderSunShadowMaps` (`stableCascade`) |
| 2 | Noise-free filter: Castano optimized bilinear PCF (hardware 2x2 taps, weighted): `r_shadowFilter` 1 = 4 taps (3x3), 2 = 9 taps (5x5), 3 = 16 taps (7x7). Replaces the per-pixel random-rotated Poisson taps (screen-fixed noise that crawled and fed SMAA speckle). Sun maps use `GL_LINEAR` + compare mode. | `glsl/shadowmask_fp.glsl` (`USE_SHADOW_SMOOTH`), `tr_image.c`, `tr_glsl.c` |
| 4 | Blend into the next cascade over the outer 10% of each map (`CASCADE_BLEND`), hides the texel-size/filter-width seam. | `shadowmask_fp.glsl` (`USE_SHADOW_CASCADE_BLEND`) |

Resolution cost of bit 1: the sphere is larger than the tight light-space box, so a cascade has up to ~1.4x
coarser texels in the best case (looking along an axis) but the same everywhere else. Split cvars
(`r_shadowCascadeZNear/ZFar/ZBias`, 8/1024/0) were left unchanged; raise `r_shadowMapSize` or lower `ZFar` to
trade.

The shadow view's PVS origin is the camera (`pvsOrigin`), since the light origin is no longer near it.
Model LOD in the shadow pass is computed against the world-origin "eye", so LOD may be coarser/finer in shadow
maps than in the main view (shadow only; watch for LOD popping in shadows).

## Verification so far
- Builds clean; shaders compile for filter 0-2 and blend; escape2 courtyard shadows render (screens in
  `benchmarks/shots/sunB-stable`, `sunC-stable`, `sunA-vanilla`).
- Bench 1920x1200, `scripts/bench.sh`: vanilla 266 fps, mode 7 252.7 fps (~5% cost: smooth 9-tap + blend).
- A scripted yaw-reprojection metric (`rot-0` vs `rot-7`) was inconclusive: residual dominated by parallax and
  specular, not shadows. **Real check is in-game**: strafe/turn near shadowed geometry in the escape2 courtyard,
  compare `r_sunShadowStable 0` vs `7` (bits individually to isolate).
- Not yet checked: edge blend seam quality, shadow LOD popping, near-parallel light/axis cases.
