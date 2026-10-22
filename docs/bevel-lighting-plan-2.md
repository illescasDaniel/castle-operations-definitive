# Bevel corners round 2: why spots 1-8 still fail and the plan (architect, 2026-10-22)

Follow-up to `docs/bevel-lighting-plan.md` (P0-P4 implemented). Repro: `scripts/shot-at.sh --map tram --label NAME
--spots-file benchmarks/spots-tram.txt --windowed 1280x720` (8 spots; always also shoot with `--set r_lightmap 1` to see
light without albedo). Shots of the pack before this round: `benchmarks/shots/arch_cur/`. Seam metric before this round
(spots 1-8): 22.7 / 2.6 / 0.6 / 4.3 / 1.9 / 7.9 / 1.8 / 14.3.

## Diagnosis

1. **Light along a strip is only defined at the strip's few geometry rows** (often >100 units apart), so the light is a
   straight line between the ends while the faces change every 16 units. The planned "extra rows" step was never
   implemented (`lm_rows_added` is never incremented; `edge_check!` only checked at those rows). This explains the dark
   bands and tone steps (spot 8 group 7528: strip ~31-34 vs faces 50-52; spot 1 group 3099: the 'strip 10% darker' with no
   engine cause). In 18.6% of tram strips the straight-line light is >10% off the face light. Also a 2x light difference
   between two faces is squeezed into a ~4.7-unit-wide strip ("lit as if sharp"), and the linear ramp makes a thin Mach
   line where the slope jumps at both strip edges.
2. **Mirrored texture mappings** (spot 8, 6): old axis-projected maps reverse the across-corner texture direction at every
   other convex corner (spot 8: -0.0074 on face A, +0.0104 on face B). The least-squares alignment only checks drift
   along the edge so it makes the textures meet exactly at the centre = perfect mirror. Tram by bevelled length: same
   shader mirrored across the corner 37.2%, axis rotated/flipped along the edge 18.6%, scale ratio >1.15 9.9%, fully
   compatible 30.7%, different shaders 14.0%.
3. Spots 1, 6, 7 are different-shader corners (`castle_m02dm` quoin vs `castle_c46_om_2`, 2x scale, sometimes mirrored): no
   UV trick makes two images continue; the hard line is the material change.
4. Global per-component offsets spread cycle errors; 470 edges (8% of length) still >0.05 repeat off.
5. Engine normal-based lighting is smooth across strips and cannot make the hard steps. Not an engine problem.

## Decisions taken (defaults, user may revise)

Mirror-flip whole same-shader components is allowed, excluding shaders matching `sign|poster|text|logo|clock|number|map|banner|flag|door|window`
(`--flip-skip`, `--no-flip`). Soft light band 12 units per face (`--soft-width`), strip radius unchanged. Different-shader
corners: wrap one material (the narrower/trim face's shader, `--wrap-prefer`) around the curve, no cross-fade overlay (F)
unless a one-corner prototype is cheap. Stretch up to 15% (`--align-stretch` 0.15). 90-degree-rotated axes: leave as is,
count them.

## Phases

- **P5 debug aids (first):** `--probe-spot "x y z yaw pitch" [--probe-fan DEG]` (rays from the camera into the tool's own
  strip/face triangles: hit kind, group, shaders, across/along texture derivatives and class, strip row t values, face
  light at the strip edge vs block light along the edge); `--seam-report FILE.tsv` (per group: class, flip decision,
  leftover offset, band stretch, light deviation) and a class-length table + row-interpolation deviation p50/p90 in
  `print_stats`; `--debug-shader uvgrid` (asymmetric F-glyph grid texture + lightmap stage on every modified surface,
  shipped in the pk3 with a .shader) ; `--debug-lm class` (false-colour block texels by class); `scripts/seam-metric.py`
  v2 (optional per-spot strip x-ranges in `benchmarks/spots-tram.regions`; strip/neighbour luminance ratio, max
  |second difference| of column means, mirror score = cross-correlation of left side vs mirrored right side around the
  strip centre, old max jump).
- **P6 strip lightmap chart:** `lmblend.jl` strip_block!/row_colours, `bevel3.jl` build_strip! (block UVs become float,
  not Int16 row/col) and assemble! uv(r,c). Texel rows every 8 units along the edge lined up with the face's lightmap texel
  centres, colours sampled at the real strip-edge line; split blocks at a geometry row and duplicate that row; keep
  endcol for caps/corners consistent. Success: block-vs-face light deviation p95 < 2% (was p90 18%); spot 8
  strip/neighbour ratio 0.63 -> >=0.95; spot 1 dip gone (ratio >=0.97 on r_lightmap 1); faces away from corners
  pixel-identical; extra pages reported (~95 -> ~130).
- **P7 texture orientation flips:** new `orient_components!(bv)` in `bevel2.jl` before `align_textures!`. Graph edges:
  bevelled seams (weight length x2) + concave seams (weight 1; collect where `rej_concave` is counted in
  `build_groups!` ~line 530). Independent +-1 flips for s and t; maximum spanning tree then greedy single-node
  improvement; in each connected group flip the side with the smaller area. Apply by negating the axis in `f.A` and
  `f.fit`. Skip (and count) rotated-axis seams. Success: mirrored length 37% -> <5%; spot 8 mirror score <0.3; uvgrid
  shots of spots 2-5, 8 show glyph orientation continuing round the corner.
- **P8 transition band for texture and light:** `bevel3.jl` cut_face!: second split at s = r + W per side, W = max(W_light
  12, width needed for stretch <= 0.15) capped at 0.45 x face width across the edge; band polygons become kind 0x04 in
  push_strip!. Texture: strip uses one shared chart C = average of both unfolded mappings + the integer offset from
  least squares; band vertices ramp from the face's own mapping at the inner line to C at the strip edge (3 sub-bands);
  fold guard where an orientation conflict remains (implements --align-stretch). Light: one chart block covers band A +
  strip + band B (<= 4-unit columns in bands), texel L' = B * lerp(L_A,in, L_B,in, S(u)) / P(u) with B the original light,
  P the current profile from strip-edge values, S a smooth S-curve; face interior and band inner line unchanged with
  zero slope; overlapping bands add as one global field. Success: strip-centre offset exactly 0 on every consistent
  same-shader seam; stretch <=15% on >95% of length; few reverted faces over vert limit; r_lightmap 1 shots show no
  thin lines at strip edges (second-difference) and max column jump <=2 at spots 2, 4-8; courses continue at 2, 4, 5, 8.
- **P9 different shaders:** in build_strip!, both halves use the chosen face's shader, unfolded continuously over the whole
  curve, blocks belong to that face. Success: no material change in the middle of the curve at spots 1, 6, 7. Option F
  (overlay cross-fade surface) only as an optional one-corner prototype.
- **P10 rollout:** `scripts/build-world.sh` all 32 maps; gates: non-finite 0, fallback faces <2%, class table logged, no
  load warnings; then all 8 tram spots (normal and r_lightmap 1), trainyard, eyeball pass.

Expected: spot 8 by P6+P7+P8; spots 1, 6, 7 by P6+P8 (light) and P9 (texture); spots 2-5 by P6+P8.
