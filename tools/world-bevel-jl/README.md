# world-bevel-jl

Julia port of `tools/world-bevel/world_bevel.py` (round convex wall corners, optional `--smooth-models` Loop
smoothing of baked props, AAS bspchecksum patch, private override pk3). Same algorithm and option names; only
the speed differs (escape1: ~110 s in Python, ~9 s here).

## Install

Julia 1.10+ (tested 1.13). Only standard-library packages are used (`LinearAlgebra`, `Printf`, `Zlib_jll`);
nothing has to be installed. The first run precompiles the package (~5 s, cached afterwards).

## Run

    julia -O2 --project=tools/world-bevel-jl tools/world-bevel-jl/world_bevel.jl \
        --map escape1 --uv-mode align --min-angle 15 --smooth-models --pk3 OUT.pk3

`--pk3` needs an explicit path. Supported: `--map --pk3 --radius --segments --taper --min-angle --max-angle
--row-tol --min-length --min-radius --skip-shader --surface-type --uv-mode --[no-]merge-polys --[no-]wall-ends
--[no-]mitre --wall-dot --smooth-models [REGEX] --no-bevel --stats`. Not ported: `--validate --roundtrip --obj
--dump-rej --region --all`. Paks are read from `run/main/*.pk3`; nothing under `run/` is written.

## Check against the Python output

    python3 -I tools/world-bevel-jl/compare_bsp.py PY.pk3 JL.pk3 escape1

Output is not byte-identical: float rounding at quantisation boundaries changes a few vertex dedupes (+-1 vertex
in ~1% of surfaces), a handful of texture shifts/colours differ by one rounding step, so the AAS checksum differs.
Surface count/order, indexes, triangle areas, bounding boxes and all other lumps match.
