# model-smooth: RTCW MDS tooling (read/write, pose, one Loop subdivision level)

Foundation for smoothing RTCW character models (skeletal `.mds`) with Loop subdivision while keeping the skin weights
exact. It has a lossless MDS reader/writer, pose evaluation (port of `R_CalcBone`), a stats report, an OBJ dump and one
Loop subdivision level (`--smooth`). Reads the 32 `body.mds` in `run/main/pak0.pk3` (heads are `.mdc`, not handled). Anything it
writes (OBJ files, reports) is derived from proprietary assets: git-ignored, never commit or redistribute.

```bash
python3 -I tools/model-smooth/model_smooth.py --roundtrip                 # parse+write all, must be 32/32 byte-identical
python3 -I tools/model-smooth/model_smooth.py --stats [GLOB]              # per-surface counts + Loop level-1 projection
python3 -I tools/model-smooth/model_smooth.py --obj models/players/infantryss/body.mds --out /tmp/f0.obj [--frame N] [--smoothed]
python3 -I tools/model-smooth/model_smooth.py --smooth '' [--crease-angle 90] [--tangential 0] [--binding base|loop] [--decal-tris 24] [--decal-area 0.05] [--decal-dist 1.5] [--min-weight 0.01] [--max-weights 4] [--pk3 run/codmod/codmod_smooth.pk3]
```

Format notes: v4 MDS has no LOD table (one surface list; LOD is per surface via `minLod` + collapse map);
`mdsWeight_t.boneIndex` is a global bone index (`boneReferences` is only the per-surface set to compute); the OBJ has
`vt` as `(s, 1-t)` and faces reversed to counter-clockwise (checked against the skinned normals).

## Subdivision (`--smooth GLOB`)

Per surface: vertices with identical weight lists are welded into topology vertices. Edges are boundary (1 triangle),
non-manifold (>2, treated as crease), crease (dihedral angle in frame 0 above `--crease-angle`) or smooth.
Odd (edge) vertices: smooth edges 3/8,3/8 + 1/8,1/8 opposite; crease/boundary 1/2,1/2. Even vertices: on a boundary
or with 1 or 3+ crease edges are pinned (seams between surfaces stay crack-free); exactly 2 crease edges use the
3/4,1/8,1/8 rule; the rest use Warren's Loop beta. Stencils blend the skin weights exactly (`W_b = sum a_i w_ib`,
`O_b = sum a_i w_ib o_ib / W_b`), then weights below `--min-weight` are dropped, the list is capped at `--max-weights`,
renormalised and sorted descending. UVs are linear (seams stay split). Each triangle becomes 4, same winding.

LOD: original vertices keep indices, UVs and collapse entries; new vertices are appended (longest welded edge first)
and collapse to the lower-index corner of their edge, so `collapseMap[j] < j` holds. `minLod` is unchanged, so the
farthest LOD is exactly the original lowest LOD; at `render_count == numOrigVerts` the original mesh comes back.
A surface that would exceed 4000 verts, 6000 verts or 8192 triangles is written unchanged (reported as KEPT).
Normals are area-weighted over weight-welded vertices in frame 0, stored in the first-weight bone frame.

Texture fidelity (stage 2b): plain Loop moves vertices tangentially, so linearly interpolated UVs slide and shear
(a painted flag waves). Only the normal component of the Loop displacement is kept (`--tangential F` keeps a fraction
F of the tangential part, default 0), so UVs stay attached to the surface. Skinning stays exact: weights bind to the
linear stencil (`--binding base`, default: identity for even vertices, 1/2,1/2 for odd; `loop` binds to the Loop
stencil) and the displacement is added to every bone offset in bone-local frame (frame-0 error < 1e-6 before pruning).
Small floating shells (<= `--decal-tris` triangles or < `--decal-area` of the largest, within `--decal-dist` of a
larger shell; `--decal-dist 0` disables) take the displacement of the closest point on the larger shell, so decals do
not detach. `--distortion [GLOB]` prints the per-surface UV-to-3D Jacobian change and stretch ratio, children vs parents.
The output pk3 is derived from RTCW models: git-ignored, never redistribute.

## MDC models (weapons, heads, props): `mdc_smooth.py`

Same normal-displacement Loop level as the MDS tool, but vertex-animated: every frame is decoded to float positions,
the stencil is applied per frame and every frame is written as an uncompressed base frame (no compressed frames).
Tags, frame bounds, shaders and original UVs are kept. Muzzle flashes (`*flash*`) and surfaces under 8 triangles are skipped.

    python3 -I tools/model-smooth/mdc_smooth.py --stats 'models/weapons2/*'
    python3 -I tools/model-smooth/mdc_smooth.py --smooth 'models/weapons2/*' --pk3 run/codmod/codmod_smooth_mdc.pk3

Output `run/codmod/codmod_smooth_mdc.pk3` is private (git-ignored). Weapons: 189 files, verts 28.6k -> ~85k.

Head models (`/head` in the path): helper surfaces of at most 40 triangles (teeth, eyelids, mouth) are not subdivided and
follow the displacement of the nearest vertex of the main surface so they do not poke through. Pack used in game:
`--smooth 'models/weapons2/*,models/players/*/head,models/players/*/head2,models/players/*/acc/*,models/powerups/*,models/mapobjects/*,models/furniture/*,models/ammo/*,models/flags/*'` (481 files, ~30 MB raw).
