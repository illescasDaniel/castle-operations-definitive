# Normals everywhere: models, characters and wall coverage (plan, 2026-10-23)

Status 2026-10-23: steps 0-5 implemented and built, uncommitted. User confirmed characters look good in game; walls and props still to be judged; step 6 (perf) and the halo fix open. Gate: user confirms each step in game. Background: `docs/parallax.md`,
`tools/height-bake/README.md`.

## Findings so far

**Models.** Weapon skins (MDC) got normals-only `_nh` maps with no engine work, because rend2 computes tangents for
MD3/MDC at load (`tr_model.c`). Character bodies are MDS (CPU-skinned in `RB_SurfaceAnim`, `tr_animation.c`), which has
no tangent code, so they need an engine change first.

**World coverage (measured with a scratch script over the BSP shader lumps).** The bake only covers shaders that
resolve to one opaque lit diffuse stage AND match `RULES` in `height_bake.py` (floor/wood/rock/concrete/brick by name).
Surfaces covered:

| Scope | baked | no-class (name matches no rule) | shader-filtered | other |
|---|---|---|---|---|
| trainyard (10.6k surfaces) | 1783 (17%) | 7684 (72%) | 1002 | 127 |
| all SP maps (300k) | 119k (40%) | 150k (50%) | 26k | 4k |

Biggest uncovered (all maps): `metal_misc/ametal_*`, `assault/metal_*`/`atool_*`, `swf/*metal*`, `broken_castle/wall_c*`
(brick walls the `brick` rule misses), `crypt/crypt_*`, `nxlab/xlab_m03`, `frogman/wall_c21`, `graveyard/gy_*`,
`terrain/mountain_m09`, `rubble/debri_*`, `awf/awf_w_*`, `chat_wood/*`, `props/box_*`. The `metal` skip rule in `RULES`
was meant for spec-bake, not for normals.

**Trainyard screenshot (user, setviewpos -1012 481 128).** Two likely causes, to confirm: (a) the dark wall is
`xlab_wall/xconcrete_c54*` / `concrete_c07`, which the confidence gate flattens (conf 0.00 for most trainyard concrete,
so heights are ~flat and DeepBump normals are weak on dark albedo); (b) the stone corner on the right is a texture with
no class (e.g. `broken_castle`/`town` wall) so it has no `_nh` at all. Not verified: no shader-name dump exists for a
view yet.

## Plan

0. **Diagnose the spot.** Add a debug cvar/console command in rend2 that prints the shader name, whether `_n`/`_nh`
   was found and whether parallax is active for the surface under the crosshair (or `r_showNormalCoverage 1`: tint
   surfaces by no-map / flat / normals / parallax). Use it on trainyard first. Also A/B `r_normalMapping 0/1` there.
1. **Widen world coverage.** Replace the name-based `RULES` with a broader classifier: default "bake" for every opaque
   lit diffuse not matched by a real exclusion (sky, glass, lights, decals, foliage, fog); add classes for metal
   (normals-only or low height, since metal wants specular, not relief), `wall_c*` brick/stone, crypt, terrain, wood
   variants, crates. Handle the 1002 shader-filtered surfaces case by case (multi-stage shaders where the lightmap
   stage is separate are fine; `tcmod`/`alphafunc` need rend2 support first). Re-bake all 32 maps (cache makes it
   ~30 s plus new textures), watch pk3 size (142 MB now).
2. **Fix weak normals on dark/flat textures.** Review the confidence gate: flattened textures should keep their
   DeepBump normals at a reduced strength (not zero), and dark albedo may need an auto-level before DeepBump
   (`autolevel` option exists). Contact-sheet the trainyard concrete before and after.
3. **Props and heads (MDC).** Bake `models/mapobjects`, `powerups`, `ammo`, `flags`, `furniture`, player heads into
   `codmod_height_models.pk3` with `--models`; exclude foliage, sky, shards, effect skins. User checks escape1/escape2.
4. **Character tangents (engine, `iortcw/`).** Compute tangents per frame in `RB_SurfaceAnim` from skinned positions +
   ST (`R_CalcTangentSpace`), gated by the normal-mapping cvar; keep LOD collapse, mirrored-UV handedness and the T2x
   velocity pass (`RB_SmaaMdsPrevPositions`) in mind; compute after `codmod_smooth.pk3` geometry.
5. **Character skins.** Bake `models/players/*` (372 skins, dedupe shared sources); one-soldier A/B first as for the
   pistol; reduce strength on skin/face textures if they look worse.
6. **Perf.** `bench.sh` (headless) before/after, plus a firefight-heavy spot for the CPU tangent cost.

Safety: no change to the rend2 present/2D path or `wolfconfig.cfg`; no new user-facing setting (reuse the Normal Maps
row); generated pk3s stay git-ignored.

## Open questions

- Metal: normals-only (keeps specular clean) or relief too?
- Include zombies/monsters/bosses in step 5, or soldiers and BJ first?

## Status 2026-10-23

- **Step 0:** `normalcov` console command (rend2) prints per-shader normal-map status for the view.
- **Step 1:** wider classifier in `height_bake.py` (about 88% of world surfaces covered; metal, props and the catch-all class get normals only) plus `--bright-target 0.30` (lifts dark albedo before DeepBump so the confidence gate stops flattening it: 229 -> 58 flattened textures). Brightening is not the cause of blobby dark stone; that is the texture itself.
- **Steps 3 and 5:** `codmod_height_models.pk3` (157 props) and `codmod_height_players.pk3` (292 skins), baked with `--models --exclude ... --models-opaque`. Skins with an effect stage 0 under the skin (supersoldier, warrior zombie head, loper) are left out because `tr_shader.c` picks one diffuse stage for the `_nh` lookup.
- **Step 4:** MDS tangents computed at runtime in `RB_SurfaceAnim` (`tr_animation.c`). User confirmed characters look good.
- **Halo around features** (dark outlines, pale fringe) is in the HD diffuse (`codmod_hd.pk3`, Real-ESRGAN), not in the normals: it persists with `r_normalMapping 0`. A gentler regeneration is in progress (candidate `run/codmod/codmod_hd_gentle.pk3.cand`).
- **Open:** about 26k surfaces whose shaders the baker skips (multi-stage, tcmod, alpha-tested), metal relief, perf check (step 6).
