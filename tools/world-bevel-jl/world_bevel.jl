#!/usr/bin/env julia
# Usage: julia -O2 --project=tools/world-bevel-jl tools/world-bevel-jl/world_bevel.jl --map escape1 --uv-mode align --min-angle 15 --smooth-models --pk3 OUT.pk3
using WorldBevel
exit(WorldBevel.main(copy(ARGS)))
