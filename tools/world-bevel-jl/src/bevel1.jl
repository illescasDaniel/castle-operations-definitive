# World bevel, part 1: data types, candidate faces, boundary edges, collinear edge matching, run (group) construction.
# Ported line by line from the original Python prototype (since removed); names are kept so old notes still match.
# Surface indexes (`si`) stay 0-based like in the BSP/Python; Julia array positions are 1-based.

const DEFAULT_SKIP = "sky|caulk|nodraw|clip|trigger|hint|fog|water|glass|decal|slime|lava|portal|skip|origin|window|" *
                     "alpha/|/sfx/|lights?/|_light|flare|cloth|curtain|lightgrid"

Base.@kwdef mutable struct Opts
    radius::Float64 = 3.0
    segments::Int = 3
    taper::Union{Nothing,Float64} = nothing
    min_angle::Float64 = 60.0
    max_angle::Float64 = 135.0
    row_tol::Float64 = 0.0
    min_length::Float64 = 4.0
    min_radius::Float64 = 1.0
    skip_shader::String = DEFAULT_SKIP
    surface_type::String = "face"
    uv_mode::String = "seam"
    merge_polys::Bool = true
    wall_ends::Bool = true
    mitre::Bool = true
    wall_dot::Float64 = 0.99
    reject_touched::Bool = true     # debug: false skips reject_touched_edges! (to test --hole-scan)
    lm_blend::Bool = true
    align_stretch::Float64 = 0.15  # max leftover texture offset (periods) between two same-shader faces that is spread over the strip (0 = off)
    flip::Bool = true               # P7: mirror-flip whole same-shader components so textures continue round corners
    flip_skip::String = "sign|poster|text|logo|clock|number|map|banner|flag|door|window"
    soft_width::Float64 = 12.0      # P8: light transition band per face
    wrap_prefer::String = "narrow"  # P9: which face's shader wraps a different-shader corner (narrow|wide)
    lm_pitch::Float64 = 12.0        # P6: units between strip lightmap rows (0 = geometry rows only, round-1 behaviour)
    debug_shader::String = ""       # P5: "uvgrid"
    debug_lm::String = ""           # P5: "class"
end

const RGB3 = NTuple{3,Float64}

struct CutVert
    gid::Int
    t::Float64
    pos::V3
end

mutable struct Face
    si::Int
    shader::Int
    name::String
    A::Vector{Att}
    tris::Vector{NTuple{3,Int}}   # 1-based indexes into A
    n::V3
    d::Float64
    planar_err::Float64
    has_lm::Bool
    centroid::V3
    winding::Int
    u::V3
    v::V3
    fit::Matrix{Float64}          # 3x4: (u, v, 1) -> (s, t, lm_s, lm_t)
    fit_err_st::Float64
    fit_err_lm::Float64
    lm_lo::NTuple{2,Float64}
    lm_hi::NTuple{2,Float64}
    polys::Union{Nothing,Vector{Poly}}
    strip::Vector{Tri}
    cutverts::Vector{CutVert}
    bad::Bool
    skind::Vector{UInt8}          # per strip triangle: 1 strip, 2 corner patch, 3 wall cap (parallel to `strip`)
    sgid::Vector{Int32}           # per strip triangle: group id (0 = corner patch)
    sblk::Vector{Int32}           # per strip triangle: lightmap block id (0 = none, keeps the face's own lightmap UVs)
    spos::Vector{NTuple{6,Float32}} # per strip triangle: (row, col) in the block for each of its 3 vertices
end

"A small grid of lightmap texels (one per strip vertex) that is copied to an appended lightmap page."
mutable struct LmBlock
    si::Int
    nr::Int
    nc::Int
    col::Vector{NTuple{3,Float64}}   # row-major, 0..255
    bx::Int; by::Int                 # position inside the new page (set by packing)
    cls::Symbol                      # seam class (debug colouring)
end

"Minimum-norm least squares like numpy.linalg.lstsq(rcond=None) (matters for rank-deficient faces)."
function lstsq_minnorm(M::Matrix{Float64}, Y::Matrix{Float64})
    F = svd(M)
    tol = eps(Float64) * max(size(M)...) * F.S[1]
    inv_s = [s > tol ? 1 / s : 0.0 for s in F.S]
    F.V * (inv_s .* (F.U' * Y))
end

function Face(si::Int, s::Surface, name::String, V::Vector{DrawVert}, I::Vector{Int32})
    vs = view(V, s.fv+1:s.fv+s.nv)
    A = Att[(Float64(v.x), Float64(v.y), Float64(v.z), Float64(v.s), Float64(v.t), Float64(v.l1), Float64(v.l2),
             Float64(v.nx), Float64(v.ny), Float64(v.nz), Float64(v.c1), Float64(v.c2), Float64(v.c3), Float64(v.c4)) for v in vs]
    nt = s.ni ÷ 3
    tris = NTuple{3,Int}[(Int(I[s.fi+3k-2]) + 1, Int(I[s.fi+3k-1]) + 1, Int(I[s.fi+3k]) + 1) for k in 1:nt]
    n = unit(V3(Float64(s.vecs[7]), Float64(s.vecs[8]), Float64(s.vecs[9])))
    nA = length(A)
    ds = [vdot(axyz(a), n) for a in A]
    d = sum(ds) / nA
    planar_err = maximum(abs.(ds .- d))
    centroid = V3(sum(a[1] for a in A) / nA, sum(a[2] for a in A) / nA, sum(a[3] for a in A) / nA)
    winding = 0
    anyb = false; allpos = true; allneg = true
    for t in tris
        g = vdot(vcross(axyz(A[t[2]]) - axyz(A[t[1]]), axyz(A[t[3]]) - axyz(A[t[1]])), n)
        if abs(g) > 1e-6
            anyb = true
            g > 0 || (allpos = false)
            g < 0 || (allneg = false)
        end
    end
    anyb && (winding = allpos ? 1 : (allneg ? -1 : 0))
    an = V3(abs(n.x), abs(n.y), abs(n.z))
    h = an.x <= an.y && an.x <= an.z ? V3(1.0, 0.0, 0.0) : (an.y <= an.z ? V3(0.0, 1.0, 0.0) : V3(0.0, 0.0, 1.0))
    u = unit(vcross(n, h))
    v = vcross(n, u)
    M = Matrix{Float64}(undef, nA, 3)
    Y = Matrix{Float64}(undef, nA, 4)
    for (i, a) in enumerate(A)
        x = axyz(a)
        M[i, 1] = vdot(x, u); M[i, 2] = vdot(x, v); M[i, 3] = 1.0
        Y[i, 1] = a[4]; Y[i, 2] = a[5]; Y[i, 3] = a[6]; Y[i, 4] = a[7]
    end
    fit = lstsq_minnorm(M, Y)
    R = M * fit - Y
    fe_st = max(maximum(abs, view(R, :, 1:2)), 0.0)
    fe_lm = max(maximum(abs, view(R, :, 3:4)), 0.0)
    has_lm = s.lmn >= 0
    lo = (Float64(s.lmx) / 128.0, Float64(s.lmy) / 128.0)
    hi = (Float64(s.lmx + s.lmw) / 128.0, Float64(s.lmy + s.lmh) / 128.0)
    Face(si, Int(s.shader), name, A, tris, n, d, planar_err, has_lm, centroid, winding, u, v, Matrix{Float64}(fit), fe_st, fe_lm, lo, hi,
         nothing, Tri[], CutVert[], false, UInt8[], Int32[], Int32[], NTuple{6,Float32}[])
end

"st, lm for a point x (projected to the plane by the basis), lm clamped to the lightmap rect."
@inline function eval_map(f::Face, x::V3)::NTuple{4,Float64}
    a = vdot(x, f.u)
    b = vdot(x, f.v)
    F = f.fit
    m1 = a * F[1, 1] + b * F[2, 1] + F[3, 1]
    m2 = a * F[1, 2] + b * F[2, 2] + F[3, 2]
    m3 = a * F[1, 3] + b * F[2, 3] + F[3, 3]
    m4 = a * F[1, 4] + b * F[2, 4] + F[3, 4]
    if f.has_lm
        h = 0.5 / 128.0   # keep the sample on texel centres inside the rect (no bleed from the neighbouring rect)
        l1, h1 = f.lm_lo[1] + h, f.lm_hi[1] - h
        l2, h2 = f.lm_lo[2] + h, f.lm_hi[2] - h
        m3 = l1 <= h1 ? min(max(m3, l1), h1) : 0.5 * (f.lm_lo[1] + f.lm_hi[1])
        m4 = l2 <= h2 ? min(max(m4, l2), h2) : 0.5 * (f.lm_lo[2] + f.lm_hi[2])
        isfinite(m3) || (m3 = 0.5 * (f.lm_lo[1] + f.lm_hi[1]))
        isfinite(m4) || (m4 = 0.5 * (f.lm_lo[2] + f.lm_hi[2]))
    end
    (m1, m2, m3, m4)
end

function nearest_color(f::Face, x::V3)::NTuple{4,Float64}
    best = 1
    bd = Inf
    @inbounds for i in 1:length(f.A)
        a = f.A[i]
        dx = a[1] - x.x; dy = a[2] - x.y; dz = a[3] - x.z
        dd = dx * dx + dy * dy + dz * dz
        if dd < bd
            bd = dd
            best = i
        end
    end
    acolor(f.A[best])
end

function ensure_polys!(f::Face)
    if f.polys === nothing
        f.polys = Poly[Att[f.A[t[1]], f.A[t[2]], f.A[t[3]]] for t in f.tris]
    end
end

"Insertion-ordered set of faces with their [t0,t1] extents along the run."
mutable struct Store
    keys::Vector{Int}
    ext::Vector{Tuple{Float64,Float64}}
end
Store() = Store(Int[], Tuple{Float64,Float64}[])
Base.in(si::Int, s::Store) = si in s.keys
Base.length(s::Store) = length(s.keys)
function store_widen!(s::Store, sid::Int, t0::Float64, t1::Float64)
    i = findfirst(==(sid), s.keys)
    if i === nothing
        push!(s.keys, sid); push!(s.ext, (t0, t1))
    else
        e = s.ext[i]
        s.ext[i] = (min(e[1], t0), max(e[2], t1))
    end
end
function store_pop!(s::Store, sid::Int)
    i = findfirst(==(sid), s.keys)
    i === nothing && return
    deleteat!(s.keys, i); deleteat!(s.ext, i)
end

mutable struct SharedPts
    pts::Union{Nothing,Vector{V3}}
end

mutable struct Mitre
    partner::Tuple{Int,Int}
    P::Int
    V::V3
    nPi::V3
    shared::SharedPts
    added::Vector{Int}
end

"One seam (bevelled run or concave edge) for the report: classes before / after the orientation pass and what was decided."
mutable struct SeamRec
    gid::Int                 # group id (0 = concave seam)
    len::Float64
    fa::Int; fb::Int         # surfaces
    shA::String; shB::String
    cls0::Symbol; cls::Symbol
    flipA::NTuple{2,Int}; flipB::NTuple{2,Int}
    resid::Float64           # leftover st offset at the seam centre (period units), NaN = not measured
    stretch::Float64
    lmdev::Float64
    der0::NTuple{8,Float64}; der1::NTuple{8,Float64}   # st derivatives (A along, A across, B along, B across) before / after the flips
    pm::V3                   # seam midpoint
end

mutable struct Row
    t::Float64
    c::Float64
    pts::Vector{V3}
    nms::Vector{V3}
end

mutable struct Group
    d::V3
    P0::V3
    nA::V3
    nB::V3
    lo::Float64
    hi::Float64
    pk::Tuple{Int,Int}
    fA::Store
    fB::Store
    wA::V3
    wB::V3
    r::Float64
    theta::Float64
    R_over_c::Float64
    corner::Vector{Bool}
    corner_te::Vector{Float64}          # NaN = none
    mitre::Vector{Union{Nothing,Mitre}}
    wall_pl::Vector{Tuple{V3,Float64}}
    wall_cap::Vector{Bool}
    wall::Vector{Bool}
    tap::Float64
    te_lo::Float64
    te_hi::Float64
    bps::Vector{Float64}
    cvals::Vector{Float64}
    ok::Bool
    row_first::Union{Nothing,Row}
    row_last::Union{Nothing,Row}
    wall_fi::Vector{Vector{Int}}        # surfaces of the wall plane at each end (for the post-cut coverage check)
end
Group(d, P0, nA, nB, lo, hi, pk, fA, fB) =
    Group(d, P0, nA, nB, lo, hi, pk, fA, fB, ZERO3, ZERO3, 0.0, 0.0, 0.0, [false, false], [NaN, NaN],
          Union{Nothing,Mitre}[nothing, nothing], [(ZERO3, 0.0), (ZERO3, 0.0)], [true, true], [false, false],
          0.0, 0.0, 0.0, Float64[], Float64[], true, nothing, nothing, [Int[], Int[]])

mutable struct Corner
    ends::Vector{Tuple{Int,Int}}
    pos::V3
    planes::Vector{Int}
end

mutable struct Bevel
    bsp::Bsp
    a::Opts
    V::Vector{DrawVert}
    I::Vector{Int32}
    S::Vector{Surface}
    names::Vector{String}
    shd::Vector{Shader}
    stats::Dict{String,Float64}
    skip_re::Union{Nothing,Regex}
    flist::Vector{Face}
    fidx::Vector{Int}
    groups::Vector{Group}
    Ep0::Vector{V3}
    Ep1::Vector{V3}
    Etv::Vector{V3}
    Ef::Vector{Int}
    coplanar_pairs::Set{Tuple{Int,Int}}
    pairs::Vector{Tuple{Int,Int,V3,V3}}
    corners::Vector{Corner}
    mitres::Vector{NTuple{4,Int}}
    wall_why::Dict{Tuple{Int,Int},String}
    end_log::Vector{String}
    lm::Vector{UInt8}             # original lightmap lump (128x128x3 pages)
    blocks::Vector{LmBlock}
    endcol::Dict{Tuple{Int,Int},Vector{NTuple{3,Float64}}}   # (group, end) -> colour of each end-row vertex
    concave::Vector{Tuple{Int,Int,V3,V3}}                    # concave edge pairs (face a, face b, p0, p1) within the bevel angle range
    seams::Vector{SeamRec}
    end_pos::Vector{V3}                                     # position of each end_log entry (--dump-rej)
    rej_log::Vector{Tuple{String,V3}}                       # rejected box-vertex corner candidates (--dump-rej)
    cap_edges::Vector{Tuple{V3,V3}}                         # wall-end edges lying on/in a wall face (--validate)
    tagged::Vector{Tuple{Int,Int,Int}}                      # (surface index, clipped tris, strip tris) per modified surface (--validate)
end

function Bevel(bsp::Bsp, a::Opts)
    S = surfaces(bsp)
    Bevel(bsp, a, verts(bsp), indexes(bsp), S, shader_names(bsp), shaders(bsp), Dict{String,Float64}(),
          isempty(a.skip_shader) ? nothing : Regex(a.skip_shader, "i"), Face[], zeros(Int, length(S)), Group[], V3[], V3[], V3[], Int[],
          Set{Tuple{Int,Int}}(), Tuple{Int,Int,V3,V3}[], Corner[], NTuple{4,Int}[], Dict{Tuple{Int,Int},String}(), String[], bsp.lumps[L_LM], LmBlock[], Dict{Tuple{Int,Int},Vector{NTuple{3,Float64}}}(), Tuple{Int,Int,V3,V3}[], SeamRec[],
          V3[], Tuple{String,V3}[], Tuple{V3,V3}[], Tuple{Int,Int,Int}[])
end

inc!(bv::Bevel, k::String, v=1) = (bv.stats[k] = get(bv.stats, k, 0.0) + v; nothing)
stat(bv::Bevel, k::String) = get(bv.stats, k, 0.0)
face(bv::Bevel, si::Int) = bv.flist[bv.fidx[si+1]]

# --- 1. candidates -------------------------------------------------------------------------------------------------
function candidates!(bv::Bevel)
    m0 = models(bv.bsp)[1]
    for si in Int(m0.fs):Int(m0.fs + m0.ns) - 1
        s = bv.S[si+1]
        if s.typ != MST_PLANAR
            inc!(bv, "surf_not_planar"); continue
        end
        nm = bv.names[s.shader+1]
        sh = bv.shd[s.shader+1]
        sf, cf = sh.sf, sh.cf
        if (sf & Int32(SURF_SKY | SURF_NODRAW | SURF_ALPHASHADOW)) != 0 ||
           (cf & Int32(CONTENTS_WATER | CONTENTS_SLIME | CONTENTS_LAVA | CONTENTS_FOG | CONTENTS_TRANSLUCENT)) != 0 ||
           (bv.skip_re !== nothing && occursin(bv.skip_re, nm)) || s.fog > 0 || s.ni < 3
            inc!(bv, "surf_skipped_shader"); continue
        end
        f = Face(si, s, nm, bv.V, bv.I)
        if f.planar_err > 0.1 || f.winding == 0 || f.fit_err_st > 2e-3 || (f.has_lm && f.fit_err_lm > 5e-4)
            inc!(bv, "surf_skipped_bad_face")
            f.bad = true
        end
        push!(bv.flist, f)
        bv.fidx[si+1] = length(bv.flist)
    end
    bv.stats["surf_candidates"] = length(bv.flist)
end

# --- 2. boundary edges ---------------------------------------------------------------------------------------------
function boundary_edges!(bv::Bevel)
    for f in bv.flist
        f.bad && continue
        ids = Dict{NTuple{3,Int64},Int}()
        wid = Vector{Int}(undef, length(f.A))
        for (i, a) in enumerate(f.A)
            wid[i] = get!(ids, (round(Int64, a[1] * 64), round(Int64, a[2] * 64), round(Int64, a[3] * 64)), length(ids) + 1)
        end
        cnt = Dict{NTuple{2,Int},Int}()
        for t in f.tris
            for slot in 1:3
                i0, i1 = slot == 1 ? (t[1], t[2]) : slot == 2 ? (t[2], t[3]) : (t[3], t[1])
                e0, e1 = wid[i0], wid[i1]
                key = (min(e0, e1), max(e0, e1))
                cnt[key] = get(cnt, key, 0) + 1
            end
        end
        for t in f.tris
            for slot in 1:3
                i0, i1, th = slot == 1 ? (t[1], t[2], t[3]) : slot == 2 ? (t[2], t[3], t[1]) : (t[3], t[1], t[2])
                e0, e1 = wid[i0], wid[i1]
                (e0 != e1 && cnt[(min(e0, e1), max(e0, e1))] == 1) || continue
                push!(bv.Ep0, axyz(f.A[i0])); push!(bv.Ep1, axyz(f.A[i1])); push!(bv.Ef, f.si); push!(bv.Etv, axyz(f.A[th]))
            end
        end
    end
    bv.stats["boundary_edges"] = length(bv.Ef)
end

# --- 3. collinear overlap pairs ------------------------------------------------------------------------------------
function match_edges!(bv::Bevel)
    n = length(bv.Ef)
    p0, p1 = bv.Ep0, bv.Ep1
    ln = Vector{Float64}(undef, n)
    ownd = Vector{V3}(undef, n)
    d = Vector{V3}(undef, n)
    for i in 1:n
        v = p1[i] - p0[i]
        ln[i] = vnorm(v)
        di = v / max(ln[i], 1e-12)
        ownd[i] = di
        ad = (round(abs(di.x), digits=3), round(abs(di.y), digits=3), round(abs(di.z), digits=3))
        lead = ad[1] >= ad[2] && ad[1] >= ad[3] ? 1 : (ad[2] >= ad[3] ? 2 : 3)
        comp = lead == 1 ? di.x : lead == 2 ? di.y : di.z
        sgn = comp > 0 ? 1.0 : (comp < 0 ? -1.0 : 1.0)
        d[i] = di * sgn
    end
    # direction clusters
    keyd = Vector{NTuple{3,Int64}}(undef, n)
    first_of = Dict{NTuple{3,Int64},Int}()
    for i in 1:n
        k = (round(Int64, d[i].x * 200), round(Int64, d[i].y * 200), round(Int64, d[i].z * 200))
        keyd[i] = k
        haskey(first_of, k) || (first_of[k] = i)
    end
    uks = sort!(collect(keys(first_of)))
    reps = V3[]
    rep_of_key = Dict{NTuple{3,Int64},Int}()
    for k in uks
        dv = d[first_of[k]]
        if !isempty(reps)
            bj = 1
            bdot = -Inf
            for (j, r) in enumerate(reps)
                dt = vdot(r, dv)
                if dt > bdot
                    bdot = dt; bj = j
                end
            end
            if bdot > 1 - 2e-5
                rep_of_key[k] = bj
                continue
            end
        end
        push!(reps, dv)
        rep_of_key[k] = length(reps)
    end
    did = [rep_of_key[keyd[i]] for i in 1:n]
    ou = Vector{Float64}(undef, n); ov = similar(ou); ou1 = similar(ou); ov1 = similar(ou)
    for i in 1:n
        D = reps[did[i]]
        aD = (abs(D.x), abs(D.y), abs(D.z))
        h = aD[1] <= aD[2] && aD[1] <= aD[3] ? V3(1.0, 0.0, 0.0) : (aD[2] <= aD[3] ? V3(0.0, 1.0, 0.0) : V3(0.0, 0.0, 1.0))
        U = vcross(D, h)
        U = U / vnorm(U)
        V = vcross(D, U)
        ou[i] = vdot(p0[i], U); ov[i] = vdot(p0[i], V)
        ou1[i] = vdot(p1[i], U); ov1[i] = vdot(p1[i], V)
    end
    cell, margin = 0.4, 0.25
    cells = Dict{NTuple{3,Int},Vector{Int32}}()
    for i in 1:n
        ln[i] > 0.5 || continue
        for cu in floor(Int, (min(ou[i], ou1[i]) - margin) / cell):floor(Int, (max(ou[i], ou1[i]) + margin) / cell)
            for cv in floor(Int, (min(ov[i], ov1[i]) - margin) / cell):floor(Int, (max(ov[i], ov1[i]) + margin) / cell)
                push!(get!(cells, (did[i], cu, cv), Int32[]), i)
            end
        end
    end
    cand = UInt64[]
    for lst in values(cells)
        for a_ in 1:length(lst)-1, b_ in a_+1:length(lst)
            push!(cand, (UInt64(lst[a_]) << 32) | UInt64(lst[b_]))
        end
    end
    sort!(cand)
    unique!(cand)
    pairs = Tuple{Int,Int,V3,V3}[]
    seams = Dict{Int,Vector{Tuple{V3,V3}}}()
    empty!(bv.coplanar_pairs)
    for code in cand
        i = Int(code >> 32)
        j = Int(code & 0xffffffff)
        bv.Ef[j] == bv.Ef[i] && continue
        q, dd = p0[i], ownd[i]
        ok = true
        tj0 = 0.0; tj1 = 0.0
        for (k, p) in enumerate((p0[j], p1[j]))
            w = p - q
            if vnorm(w - vdot(w, dd) * dd) > 0.15
                ok = false
                break
            end
            k == 1 ? (tj0 = vdot(w, dd)) : (tj1 = vdot(w, dd))
        end
        ok || continue
        lo, hi = max(0.0, min(tj0, tj1)), min(ln[i], max(tj0, tj1))
        hi - lo < 0.25 && continue
        fi, fj = face(bv, bv.Ef[i]), face(bv, bv.Ef[j])
        if vdot(fi.n, fj.n) > 1 - 1e-4 && abs(fi.d - fj.d) < 0.1
            push!(bv.coplanar_pairs, (fi.si, fj.si))
            ti = bv.Etv[i] - q
            tk = bv.Etv[j] - q
            si_ = ti - vdot(ti, dd) * dd
            sk_ = tk - vdot(tk, dd) * dd
            if vdot(si_, sk_) < 0
                push!(get!(seams, i, Tuple{V3,V3}[]), (q + dd * lo, q + dd * hi))
                push!(get!(seams, j, Tuple{V3,V3}[]), (q + dd * lo, q + dd * hi))
            end
        end
        push!(pairs, (i, j, q + dd * lo, q + dd * hi))
    end
    out = Tuple{Int,Int,V3,V3}[]
    for (i, j, pa, pb) in pairs
        if vdot(face(bv, bv.Ef[i]).n, face(bv, bv.Ef[j]).n) > 1 - 1e-4
            push!(out, (i, j, pa, pb))
            continue
        end
        ln_ = vnorm(pb - pa)
        dd = (pb - pa) / max(ln_, 1e-12)
        cut = Tuple{Float64,Float64}[]
        for s in (get(seams, i, Tuple{V3,V3}[]), get(seams, j, Tuple{V3,V3}[]))
            for (s0, s1) in s
                a0, a1 = vdot(s0 - pa, dd), vdot(s1 - pa, dd)
                push!(cut, (max(0.0, min(a0, a1)), min(ln_, max(a0, a1))))
            end
        end
        sort!(cut)
        segs = Tuple{Float64,Float64}[]
        t = 0.0
        for (c0, c1) in cut
            c1 <= c0 && continue
            c0 - t >= 0.25 && push!(segs, (t, c0))
            t = max(t, c1)
        end
        ln_ - t >= 0.25 && push!(segs, (t, ln_))
        if length(segs) == 1 && segs[1] == (0.0, ln_)
            push!(out, (i, j, pa, pb))
            continue
        end
        inc!(bv, isempty(segs) ? "pairs_seam_removed" : "pairs_seam_trimmed")
        for (s0, s1) in segs
            push!(out, (i, j, pa + dd * s0, pa + dd * s1))
        end
    end
    bv.pairs = out
    bv.stats["edge_pairs_collinear_overlap"] = length(out)
end

# --- 4. classify pairs and build groups ----------------------------------------------------------------------------
function line_frame(nA::V3, dA::Float64, nB::V3, dB::Float64)
    d = unit(vcross(nA, nB))
    P0 = solve3((nA, nB, d), (dA, dB, 0.0))
    P0 === nothing && error("singular plane pair")
    d, P0
end

mutable struct Acc
    fa::Face
    fb::Face
    seg::Vector{Tuple{V3,V3}}
    fseg::Vector{Tuple{Int,Int,V3,V3}}
end

function build_groups!(bv::Bevel)
    a = bv.a
    cos_min, cos_max = cos(deg2rad(a.max_angle)), cos(deg2rad(a.min_angle))
    planes = Dict{NTuple{4,Int},Int}()
    plane_id(f::Face) = get!(planes, (round(Int, f.n.x * 500), round(Int, f.n.y * 500), round(Int, f.n.z * 500), round(Int, f.d / 0.25)), length(planes))
    acc = Dict{Tuple{Int,Int},Acc}()
    acc_order = Tuple{Int,Int}[]
    for (i, j, pa, pb) in bv.pairs
        fa, fb = face(bv, bv.Ef[i]), face(bv, bv.Ef[j])
        c = vdot(fa.n, fb.n)
        if c > 1 - 1e-4
            inc!(bv, "rej_coplanar"); continue
        end
        if !(cos_min <= c <= cos_max)
            inc!(bv, "rej_angle"); continue
        end
        if !(vdot(fb.n, fa.centroid) - fb.d < -0.05 && vdot(fa.n, fb.centroid) - fa.d < -0.05)
            inc!(bv, "rej_concave")
            push!(bv.concave, (fa.si, fb.si, pa, pb))
            continue
        end
        ia, ib = plane_id(fa), plane_id(fb)
        if ia > ib
            fa, fb, ia, ib = fb, fa, ib, ia
        end
        g = get(acc, (ia, ib), nothing)
        if g === nothing
            g = Acc(fa, fb, Tuple{V3,V3}[], Tuple{Int,Int,V3,V3}[])
            acc[(ia, ib)] = g
            push!(acc_order, (ia, ib))
        end
        push!(g.seg, (pa, pb))
        inc!(bv, "pairs_convex")
        push!(g.fseg, (fa.si, fb.si, pa, pb))
    end
    for key in acc_order
        g = acc[key]
        fa, fb = g.fa, g.fb
        nA, nB = fa.n, fb.n
        d, P0 = line_frame(nA, fa.d, nB, fb.d)
        ivs = Tuple{Float64,Float64}[]
        for (pa, pb) in g.seg
            t0, t1 = vdot(pa - P0, d), vdot(pb - P0, d)
            push!(ivs, (min(t0, t1), max(t0, t1)))
        end
        sort!(ivs)
        merged = Vector{Float64}[]
        for (lo, hi) in ivs
            if !isempty(merged) && lo <= merged[end][2] + 1.0
                merged[end][2] = max(merged[end][2], hi)
            else
                push!(merged, [lo, hi])
            end
        end
        for (lo, hi) in merged
            fAs, fBs = Store(), Store()
            for (sa, sb, pa, pb) in g.fseg
                t0, t1 = vdot(pa - P0, d), vdot(pb - P0, d)
                t0, t1 = min(t0, t1), max(t0, t1)
                (t1 < lo - 1e-3 || t0 > hi + 1e-3) && continue
                store_widen!(fAs, sa, t0, t1)
                store_widen!(fBs, sb, t0, t1)
            end
            push!(bv.groups, Group(d, P0, nA, nB, lo, hi, key, fAs, fBs))
        end
    end
    bv.stats["groups_candidate"] = length(bv.groups)
end
