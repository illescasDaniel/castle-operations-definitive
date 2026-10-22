# Bevel corners: continuous lighting, connected textures, white hole

Status: approved by the user 2026-10-22, implementation in progress. Tool: `tools/world-bevel-jl/src` (`bevel1.jl`
eval_map/mkatt, `bevel2.jl` align_textures!, `bevel3.jl` build_strip!/assemble!, `bspio.jl`, `cli.jl`).

## Problem (repro: `scripts/shot-at.sh --map tram --label NAME --spots-file benchmarks/spots-tram.txt --windowed 1280x720`)

Baseline shots: `benchmarks/shots/tram_base/spot0N.tga`. Geometry is fine. On rounded corners:

1. A perfectly vertical light step where the two strip halves meet (each half uses its own face's lightmap page and
   clamps to that face's edge texel). Measured baseline seam jump (column-mean luminance, 0-255): spot02 15.8
   (right/left 0.53), spot04 8.5 (1.79), spot05 5.5 (0.61).
2. Stone courses offset across the same line (greedy per-component constant st shift cannot satisfy loops; different
   shaders and drift/scale runs are skipped; ~20-25% of runs skipped silently as cycles).
3. A small white triangle at a wall end (spot01 lower right, spot03 user report).

## Renderer facts

- Lightmapped world shaders ignore drawvert colour (`rgbGen identity`), so vertex-colour fades need an engine change.
- `r_mergeLightmaps 1` packs pages into an atlas; only vertex lm UVs matter (engine ignores lmx/lmy/lmw/lmh).
- Deluxe mapping is only on when no surface has an odd `lmn`; appended pages must not flip that check.
- Strip normals are already smooth; the step is purely lightmap.

## Phases (verify on the 5 tram spots after each)

- **P0 diagnostics:** `--dump-near X Y Z R` in cli.jl (strip/cap/corner tris near a point: source face, shader, lmn, rect,
  lm UVs, clamped flag, finite flag), tool stats (non-finite lm count, has_lm=false strips/caps, strips whose halves sit on
  different pages, median/p95 luminance step), `scripts/seam-metric.py` (per shot: max adjacent-column jump and
  right/left ratio), an `r_lightmap 1` shot set.
- **P1 white hole / hygiene:** clamp lm to texel centres `[lo+0.5/128, hi-0.5/128]`, `isfinite` guards, reject or fall back
  non-finite triangles, choose cap/corner face by plane membership.
- **P2 continuous lighting (main work):** for each surface with strip/cap/corner triangles copy its lightmap rect into an
  appended 128x128 page (1-texel replicate gutter, texel aligned, UVs translate), add per-strip blocks (one texel per strip
  vertex): half A = lerp(L_A(row), M(row), smoothstep(arc)), half B mirrored toward L_B, M = 0.5(L_A+L_B) per channel
  (L from bilinear samples of the original lump at each cut line). Add rows adaptively at lightmap pitch where linear
  interpolation deviates >6% (watch MAX_BEVEL_FACE_VERTS). Fallback to old behaviour if a page does not fit (count it).
  Corner patches: average of the faces' edge values. Keep at least one odd lmn. Success: median |dY|/Y < 3% (p95 < 10%),
  seam jump on spots 02/04/05 <= ~2 levels, faces away from corners pixel-identical to baseline. Fallback: engine lightall
  multiplies lightmapped stages by vertex colour (user allowed trying it).
- **P3 connected textures:** replace greedy `align_textures!` with a global least-squares solve of per-component affine st
  offsets over sampled seam points (integer lifts from a spanning tree, re-rounded and re-solved), stretch cap
  `--align-stretch` 0.15, silent cycle skips counted, `--uv-mode align-greedy` kept for A/B. Same-shader seams first; if the
  result is not good enough also handle different-shader seams (same-image shader equivalence, then dominant shader).
  Success: same-shader seam residual < 0.05 period on >90% of length on tram/escape1; courses line up on spots 02/04/05.
- **P4 rollout:** `scripts/build-world.sh` for all maps (pass `--stats` so logs keep it); gate on non-finite 0, fallbacks <2%,
  no load warnings; visually spot-check one more map.

User decisions: smooth luminance cross-fade is acceptable; larger atlas is acceptable; stretch up to ~15% acceptable.
