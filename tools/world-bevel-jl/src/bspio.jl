# RTCW IBSP v47 container: lumps are kept as raw bytes (all but 10/11/13 are copied verbatim), typed views are copies.

const IDENT = UInt8[0x49, 0x42, 0x53, 0x50]  # "IBSP"
const VERSION = 47
const NLUMPS = 17
const HEADER_SIZE = 8 + NLUMPS * 8
const L_ENT, L_SHADER, L_PLANE, L_NODE, L_LEAF, L_LSURF, L_LBRUSH, L_MODEL, L_BRUSH, L_BSIDE, L_VERT, L_INDEX, L_FOG, L_SURF, L_LM, L_GRID, L_VIS =
    1:17  # 1-based lump numbers (Python: 0..16)

struct DrawVert  # 44 bytes
    x::Float32; y::Float32; z::Float32
    s::Float32; t::Float32
    l1::Float32; l2::Float32
    nx::Float32; ny::Float32; nz::Float32
    c1::UInt8; c2::UInt8; c3::UInt8; c4::UInt8
end

struct Surface  # 104 bytes
    shader::Int32; fog::Int32; typ::Int32
    fv::Int32; nv::Int32; fi::Int32; ni::Int32
    lmn::Int32; lmx::Int32; lmy::Int32; lmw::Int32; lmh::Int32
    org::NTuple{3,Float32}
    vecs::NTuple{9,Float32}
    pw::Int32; ph::Int32
end

struct Shader  # 72 bytes
    name::NTuple{64,UInt8}
    sf::Int32; cf::Int32
end

struct Model  # 40 bytes
    mins::NTuple{3,Float32}; maxs::NTuple{3,Float32}
    fs::Int32; ns::Int32; fb::Int32; nb::Int32
end

@assert sizeof(DrawVert) == 44 && sizeof(Surface) == 104 && sizeof(Shader) == 72 && sizeof(Model) == 40

const MST_PLANAR, MST_PATCH, MST_TRISOUP, MST_FLARE = 1, 2, 3, 4
const SURF_SKY, SURF_NODRAW, SURF_ALPHASHADOW = 0x4, 0x80, 0x10000
const CONTENTS_WATER, CONTENTS_SLIME, CONTENTS_LAVA, CONTENTS_FOG, CONTENTS_TRANSLUCENT = 0x20, 0x10, 0x8, 0x40, 0x20000000
const MAX_BEVEL_FACE_VERTS = 1024

function from_bytes(::Type{T}, b::AbstractVector{UInt8}) where {T}
    n = length(b) ÷ sizeof(T)
    out = Vector{T}(undef, n)
    GC.@preserve out b unsafe_copyto!(Ptr{UInt8}(pointer(out)), pointer(b), n * sizeof(T))
    out
end

function to_bytes(a::AbstractVector{T}) where {T}
    out = Vector{UInt8}(undef, length(a) * sizeof(T))
    GC.@preserve out a unsafe_copyto!(pointer(out), Ptr{UInt8}(pointer(a)), length(out))
    out
end

mutable struct Bsp
    table::Vector{Tuple{Int,Int}}
    lumps::Vector{Vector{UInt8}}
    order::Vector{Int}
    pad::Vector{Vector{UInt8}}
end

function Bsp(data::Vector{UInt8})
    (view(data, 1:4) == IDENT && le32(data, 4) == VERSION) || error("not an RTCW IBSP v47 file")
    table = [(Int(le32(data, 8 + 8i)), Int(le32(data, 12 + 8i))) for i in 0:NLUMPS-1]
    lumps = [data[o+1:o+l] for (o, l) in table]
    order = sortperm(table)  # by (offset, length); on-disk order is kept
    pad = [UInt8[] for _ in 1:NLUMPS]
    for (k, i) in enumerate(order)
        en = table[i][1] + table[i][2]
        nxt = k < NLUMPS ? table[order[k+1]][1] : length(data)
        pad[i] = (0 <= nxt - en < 4) ? data[en+1:nxt] : UInt8[]
    end
    Bsp(table, lumps, order, pad)
end

function write_bsp(b::Bsp)
    out = zeros(UInt8, HEADER_SIZE)
    table = Vector{Tuple{Int,Int}}(undef, NLUMPS)
    for i in b.order
        table[i] = (length(out), length(b.lumps[i]))
        append!(out, b.lumps[i])
        need = mod(-length(out), 4)
        if !isempty(b.pad[i])
            append!(out, (vcat(b.pad[i], zeros(UInt8, 4)))[1:need])
        else
            append!(out, zeros(UInt8, need))
        end
    end
    out[1:4] .= IDENT
    out[5:8] .= reinterpret(UInt8, [Int32(VERSION)])
    for (i, (o, l)) in enumerate(table)
        out[9+8(i-1):12+8(i-1)] .= reinterpret(UInt8, [Int32(o)])
        out[13+8(i-1):16+8(i-1)] .= reinterpret(UInt8, [Int32(l)])
    end
    out
end

verts(b::Bsp) = from_bytes(DrawVert, b.lumps[L_VERT])
indexes(b::Bsp) = from_bytes(Int32, b.lumps[L_INDEX])
surfaces(b::Bsp) = from_bytes(Surface, b.lumps[L_SURF])
shaders(b::Bsp) = from_bytes(Shader, b.lumps[L_SHADER])
models(b::Bsp) = from_bytes(Model, b.lumps[L_MODEL])

cstr(t::NTuple{N,UInt8}) where {N} = (z = findfirst(==(0x00), t); String(UInt8[t[i] for i in 1:(z === nothing ? N : z - 1)]))
shader_names(b::Bsp) = [cstr(s.name) for s in shaders(b)]

with_geometry(s::Surface; typ=s.typ, fv=s.fv, nv=s.nv, fi=s.fi, ni=s.ni) =
    Surface(s.shader, s.fog, Int32(typ), Int32(fv), Int32(nv), Int32(fi), Int32(ni), s.lmn, s.lmx, s.lmy, s.lmw, s.lmh, s.org, s.vecs, s.pw, s.ph)

with_lm(s::Surface; lmn=s.lmn, lmx=s.lmx, lmy=s.lmy) =
    Surface(s.shader, s.fog, s.typ, s.fv, s.nv, s.fi, s.ni, Int32(lmn), Int32(lmx), Int32(lmy), s.lmw, s.lmh, s.org, s.vecs, s.pw, s.ph)

with_shader(s::Surface, shader) =
    Surface(Int32(shader), s.fog, s.typ, s.fv, s.nv, s.fi, s.ni, s.lmn, s.lmx, s.lmy, s.lmw, s.lmh, s.org, s.vecs, s.pw, s.ph)

"Copy of `b` whose vertex / index / surface lumps are replaced."
function replace_lumps(b::Bsp, V::Vector{DrawVert}, I::Vector{Int32}, S::Vector{Surface})
    out = Bsp(copy(b.table), copy(b.lumps), copy(b.order), copy(b.pad))
    out.lumps[L_VERT] = to_bytes(V)
    out.lumps[L_INDEX] = to_bytes(I)
    out.lumps[L_SURF] = to_bytes(S)
    out
end

# --- paks -------------------------------------------------------------------------------------------------------------
pak_list(root) = sort(filter(p -> endswith(p, ".pk3"), readdir(joinpath(root, "run/main"), join=true)))

function find_in_paks(root, pred)
    found = Dict{String,Vector{UInt8}}()
    for p in pak_list(root)
        for e in zip_entries(p)
            pred(e.name) && (found[e.name] = zip_read(p, e))
        end
    end
    found
end

function find_bsp(root, name)
    rel = "maps/$name.bsp"
    data = nothing
    for p in pak_list(root)
        for e in zip_entries(p)
            e.name == rel && (data = (p, e))
        end
    end
    data === nothing && error("maps/$name.bsp not found in $(joinpath(root, "run/main"))")
    zip_read(data[1], data[2])
end

function find_aas(root, name)
    rx = Regex("^maps/" * replace(name, r"([^\w])" => s"\\\1") * "(_b\\d+)?\\.aas\$")
    find_in_paks(root, n -> occursin(rx, n))
end
