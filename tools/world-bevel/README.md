# world-bevel: round convex wall corners in RTCW maps (visual only, prototype)

Reads `maps/NAME.bsp` from `run/main/*.pk3` (later paks override earlier) and writes `run/codmod/codmod_bevel.pk3`
with a modified `maps/NAME.bsp`. Output is derived from proprietary maps: git-ignored, never commit. Python 3 + numpy.

```bash
python3 -I tools/world-bevel/world_bevel.py --roundtrip [--all]          # parse+write must be byte-identical
python3 -I tools/world-bevel/world_bevel.py --map escape1 --stats        # counts per rejection reason
python3 -I tools/world-bevel/world_bevel.py --map escape1 --validate     # sanity checks on the result
python3 -I tools/world-bevel/world_bevel.py --map escape1 --obj /tmp/c.obj --region x0 y0 z0 x1 y1 z1   # _before/_after.obj
python3 -I tools/world-bevel/world_bevel.py --map escape1 --pk3 [run/codmod/codmod_bevel.pk3]
```

Options: `--radius 3` (setback of the cut from the edge on each face; the arc radius is `radius/tan(theta/2)`),
`--segments 3`, `--taper 2*radius`, `--min-angle 60 --max-angle 135` (angle between the two face normals),
`--min-length 4`, `--min-radius 1`, `--skip-shader REGEX`, `--surface-type face|tri`, `--uv-mode seam|morph|align` (default seam; align: shift whole coplanar face groups so textures continue across the edge, minor effect; morph: when both faces
of a run share a shader and their texture scales differ by <= 1.5x, st is blended smoothstep-wise from face A's mapping
to face B's mapping shifted by an integer, so the texture runs through the rounded corner; lightmaps stay per half).

How it works: only lumps 10/11/13 change (surface count/order, collision lumps untouched). Boundary edges of planar
world faces are matched by collinear overlap (T-junction safe), kept when convex and in the angle window, merged per
plane pair into runs, then each face is clipped back by `radius` (linear taper to 0 at both run ends) and a
circular-arc strip is added; strip halves get each face's own affine st/lightmap mapping (lightmap clamped to the
surface rect) and are appended to that face's surface. Modified surfaces get new vert/index ranges appended to the
lumps (old ranges stay as unused data).

Caveats: default `--surface-type face` keeps type 1 (lightmap kept) and needs the engine patch (rend2 `ParseFace`:
`BSP_MAX_FACE_VERTS` 1024 instead of 64, and no plane cull when verts are > 0.25 off the face plane). A face that
would exceed 1024 verts is left unbevelled. `--surface-type tri` converts to type 3, which rend2 lights by vertex
colour only. Runs are dropped when their cut region overlaps another run on the same face or is not fully covered by the
face. Concave corners, patches and brush entities are not handled. Strips add ~100k triangles on escape1.

Round 4: each run uses an adaptive radius `min(--radius, 0.45 x smallest face extent from the edge)` (skipped below
`--min-radius`), taper `min(2r, len/3)`. Three convex runs ending at one orthogonal box vertex are not tapered: the strips stop
at the corner of the clipped faces and a spherical patch closes the gap. `--pk3` also writes `maps/NAME*.aas` with the
`bspchecksum` re-patched to the new BSP (pure-Python MD4; the collision lumps are unchanged, so the bots' areas stay valid).
Edge matching tolerates tilted direction clusters (previously about 20% of long edges were never paired).

Round 5 (run ends): a run end is no longer always tapered.
- Wall ends (`--wall-ends`, default on, `--wall-dot 0.99`): when the end vertex lies on another face plane W and the run
  heads straight into it (a ledge butting into a wall), the full radius is kept up to W. The strip end row is slid onto W and
  snapped to the clipped-face end vertices. If W is already drawn under the ledge nothing more is needed; if W has a hole
  boundary there, a triangle fan in plane W fills the notch (st/lm from the run's face A, same vertex format). Any failed
  condition (no plane, no hole boundary, overlap, coverage) falls back to the taper.
- Mitre (`--mitre`, default on): two orthogonal runs of the same plane P with equal radius and dihedral that meet at a
  reflex (L-shaped) bend. The cut continues r past each run end on P (faces of P covering the corner square are added to the
  run's face set), and both strips end in one shared row on the bisector plane, so the rounded edge turns the bend without
  taper. Faces wrapping behind the cut line are left alone by `cut_face`.
- `--dump-rej X0 Y0 Z0 X1 Y1 Z1` lists the end kind (corner, wall, mitre, two, nobox, taper:why) of runs in a box.
- Validation: wall-end rows/caps lie on the wall face, so those edges are excluded from the strip-crack count
  (reported as "wall-end edges excluded"). Escape1, radius 5: longer-unmatched strip edges 197 (before 199), indexes
  1.28M (before 1.36M, fewer taper strips), 3064 wall ends (89 caps, 356 tris), 383 mitres. Known leftovers: ends beside
  1-unit sliver faces still taper (rej_thin_face); the wall-end cap uses face A's st/lm mapping.
- Seams (fix for white slivers in the gaps between stepped blocks on escape1, near (1586..1592, 1150..1167, -784)): a
  convex pair stretch is dropped where the edge of face A (or B) also touches a coplanar face C on the far side of the
  same line. There the edge is a seam inside one flat surface and the "riser" B is a buried face (a stock riser quad spans
  the whole step while the neighbouring block's top continues flush), so bevelling it cut a groove whose slit let the
  camera see into the solid, white void shows through. `match_edges` trims the stretch (`pairs_seam_trimmed/removed` stats).
- `--min-angle 15` (default 60): 1.40M indexes (+9%), 223 longer-unmatched, all other checks pass; still well under the
  rend2 VAO cache of 1<<22 indexes for this map.

## Performance

The real requirement is the engine fix: rend2's VAO cache must be big enough (`VAOCACHE_VERTEX_BUFFER_SIZE` 1<<20 verts,
`VAOCACHE_INDEX_BUFFER_SIZE` 1<<22 indexes in `rend2/tr_vbo.c`). With it, the full-coverage pack (1.4M indexes) runs
at stock FPS; without it the cache recycles every frame and FPS halves. `r_vaoCacheStats 1` (cheat) or `r_speeds 9`
prints recycles per frame and fill. Triangle count is secondary.

Lossless savings kept on by default: stock ranges of rewritten surfaces are dropped and the lumps laid out compactly,
and clipped face pieces are merged into convex polygons (flip fallback per face; `--no-merge-polys` disables).
Optional size cuts, off by default because they cost coverage or add cracks: `--segments 2`, larger `--min-length`
(16 skips many 16-unit box corners), and `--row-tol 0.05` (thins strip rows but raises longer unmatched strip edges
from about 200 to about 1450; the default 0 keeps every row).

## Connected textures (`--uv-mode align`)

Strip texture coordinates are unfolded by arc length from each face's cut line, and whole coplanar-connected face groups
are shifted by the non-integer st mismatch measured at the arc middle (greedy forest, longest runs first). Limits:
- Runs between different shaders cannot align (about 2100 on escape1); each half keeps its own face's mapping.
- Runs whose mapping drifts along the edge (about 560) or whose texture scales differ >1.5x (about 75) are skipped.
- Each face group is shifted at most once, so edges closing a loop of faces can still show a phase jump.
- Effect: stone courses wrap around rounded corners; shifted faces can move their texture up to half a period.

## Baked models (`--smooth-models [REGEX]`)

Misc_model props compiled into the BSP (torches, cage lights, chandeliers, furniture) are trisoup surfaces. This option
runs the same one-level Loop smoother as `tools/model-smooth/mdc_smooth.py` (normal displacement only, 90° crease angle,
boundary pinned) on trisoup surfaces whose shader matches the regex (default `DEFAULT_SMOOTH`: `models/*` except players,
plus `textures/(props|metal_misc|wood|chat)/`; trees, rock and terrain are left alone). It runs after the bevel in the same
pack (one BSP per map, so both must share a pack); `--no-bevel` smooths only. escape1: 208 surfaces, 17k -> 69k tris.

`--smooth-models` also smooths **brush props** (`smooth_brush_props`): torches, brackets and small crates are plain type 1 faces of the
world model. Faces matching `DEFAULT_BRUSH_PROPS` (`textures/(props|metal_misc|wood|town_wood|chat)/`) that touch (welded by
position) form one mesh; groups of at least 6 faces and at most 100 units wide are Loop-smoothed together and split back to the
stock surfaces (count, shaders and lightmap pages unchanged). escape1: 102 props (1670 surfaces); the torch goes 256 -> 676 tris.
