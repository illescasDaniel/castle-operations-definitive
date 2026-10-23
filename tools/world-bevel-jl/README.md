# world-bevel-jl

The world-bevel tool: rounds convex wall corners of RTCW maps (visual only), optional `--smooth-models` Loop smoothing
of baked props, continuous corner lighting and connected textures, AAS bspchecksum patch, private override pk3. It is the
only implementation (the earlier Python prototype was removed); escape1 takes ~9 s.

## Install

Julia 1.10+ (tested 1.13). Only standard-library packages are used (`LinearAlgebra`, `Printf`, `Zlib_jll`);
nothing has to be installed. The first run precompiles the package (~5 s, cached afterwards).

## Run

    julia -O2 --project=tools/world-bevel-jl tools/world-bevel-jl/world_bevel.jl \
        --map escape1 --uv-mode align --min-angle 15 --smooth-models --pk3 OUT.pk3

`--pk3 [OUT.pk3]` (default `run/codmod/codmod_bevel.pk3`). Options: `--map --pk3 --radius --segments --taper --min-angle
--max-angle --row-tol --min-length --min-radius --skip-shader --surface-type --uv-mode --[no-]merge-polys --[no-]wall-ends
--[no-]mitre --wall-dot --smooth-models [REGEX] --no-bevel --stats`, plus the checks below and Julia-only tuning
(`--[no-]lm-blend --[no-]flip --align-stretch --soft-width --wrap-prefer --lm-pitch`, debug: `--dump-near --probe-spot
--seam-report --debug-shader --debug-lm`). Paks are read from `run/main/*.pk3`; nothing under `run/` is written unless `--pk3` says so.

## Checks and exports

    ... --roundtrip [--all]                     # parse + write must be byte-identical (--all: every map; 32/32 today)
    ... --map escape1 --validate                # sanity checks on the result (exit code 1 on a FAIL)
    ... --map escape1 --obj OUT.obj --region x0 y0 z0 x1 y1 z1   # OUT_before.obj / OUT_after.obj, triangles whose centroid is in the box
    ... --map escape1 --dump-rej x0 y0 z0 x1 y1 z1               # run-end kinds (corner, wall, mitre, taper:why, two, nobox...) in a box

`--validate` checks index/vertex ranges, surface count, NaN, shader/fog/lightmap numbers, other lumps, degenerate triangles,
lightmap coords inside the surface rect, strip/winding orientation and that strip boundary edges meet a clipped face edge.
With lightmap blending (default) the lightmap lump may only grow, blended surfaces may move to the appended pages and their
strip vertices are checked against the page instead of the rect. The last check ("longer unmatched", ~130-440 per map) fails on
the stock RTCW geometry too (the old Python tool reported the same order); `WB_GAPS=1` lists all of them. A few maps (dam) also
report some lightmap coords outside the rect (11 with the Python tool, 20 here).

## Build all maps

    scripts/build-world.sh            # all maps, JOBS=8 in parallel (~25 s total); or name maps: scripts/build-world.sh escape1
    JOBS=16 scripts/build-world.sh    # more/fewer parallel single-threaded map jobs

Each map writes its own log to `benchmarks/world-MAP.log` and builds into `codmod_bevel_MAP.pk3.tmp`, which replaces the
pack only on success; the script ends with `failed: ...` listing maps whose job failed.

White-hole fixes (`reject_touched_edges!` in `bevel2.jl`: a convex
edge is left un-rounded when a foreign surface touches it mid-run, when two solids touch diagonally along one edge line,
and box-vertex mitres whose third edge is sharp become tapers; the mitre check runs again after `drop_overlapping!`, which can
drop that third edge). Pack deflate level is 6 (level 9 cost most of the build
time for ~1% size).

## Hole check (`--hole-scan`)

    WB_SCAN_DUMP=holes.tsv julia -O2 --project=tools/world-bevel-jl tools/world-bevel-jl/world_bevel.jl --map escape1 \
        --uv-mode align --min-angle 15 --hole-scan        # no --pk3 needed

Topological post-check of the final rounded runs (independent of the rejection rules, so it can catch their gaps):
every rounded run whose removed wedge may be uncovered. It prints one count per category plus the first few locations;
`WB_SCAN_DUMP` writes all of them as TSV (`category run x y z note`, world coordinates, run = group id). Categories:

- `touched`: a foreign surface's boundary edge (with a vertex on the line) lies on the run's edge line mid-run. The
  known hole cause; the rules reject these, so expect 0.
- `diagonal`: two rounded runs on one line with opposite-side wedges (solids touching diagonally). The rule only
  rejects wedges with dot < -0.5; this reports > -0.05, so a few near-90 degree cases remain.
- `overlap`: two rounded runs on one line sharing a face (double cut).
- `mitre3` / `corner3`: a box-vertex mitre or corner end with fewer than three rounded edges at the vertex (a later
  rejection, e.g. overlap, removed the third edge after the mitre check ran).
- `tee`: a foreign boundary edge crosses the line without a vertex on it. Hundreds per map; not known to open a visible
  slit (likely benign when the foreign face is hidden back to back), so treat it as informational.

To test the detector, add `--no-reject-touched` (skips `reject_touched_edges!`): escape1 then reports the known holes
(runs 8106 at 584,704; 7138/8107 at 608,704; mitre3 7142/7273 at 572,672,-560). A healthy normal build has `touched 0`
and `mitre3 0`/`corner3 0`.
