module WorldBevel

using LinearAlgebra: svd
using Printf
import Zlib_jll

include("zipio.jl")
include("bspio.jl")
include("geometry.jl")
include("smooth.jl")
include("bevel1.jl")
include("bevel2.jl")
include("bevel3.jl")
include("diag.jl")
include("lmblend.jl")
include("holes.jl")
include("cli.jl")

# compile the whole call tree at package precompile time (cached), so the first run does not spend ~10 s in the JIT
precompile(main, (Vector{String},))

end
