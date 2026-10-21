# One-level Loop smoother (normal displacement only), single frame: port of tools/model-smooth/mdc_smooth.py smooth_surface
# plus the two BSP users (baked trisoup models, brush props) from world_bevel.py.

const SHADER_MAX_VERTEXES = 4000
const SHADER_MAX_INDEXES = 6 * SHADER_MAX_VERTEXES

struct SmoothResult
    Pn::Vector{V3}
    Nn::Vector{V3}
    uvn::Vector{NTuple{2,Float64}}
    ot::Vector{NTuple{3,Int}}       # 1-based vertex indexes
    pv::Vector{NTuple{2,Int}}       # 1-based original vertex pair of every new vertex
    before_t::Int
    after_t::Int
end

# returns (result or nothing, reason)
function smooth_surface(P::Vector{V3}, N::Vector{V3}, tris::Vector{NTuple{3,Int}}, uv::Vector{NTuple{2,Float64}}; crease_angle=90.0)
    n = length(P)
    T = length(tris)
    # weld vertices that coincide
    keys = Dict{NTuple{3,Int32},Int}()
    wel = Vector{Int}(undef, n)
    for i in 1:n
        k = (Int32(round(P[i].x * 64.0)), Int32(round(P[i].y * 64.0)), Int32(round(P[i].z * 64.0)))
        wel[i] = get!(keys, k, length(keys) + 1)
    end
    nt_ = length(keys)
    rep = zeros(Int, nt_)
    for i in n:-1:1
        rep[wel[i]] = i
    end
    tp = V3[P[rep[t]] for t in 1:nt_]
    tt = NTuple{3,Int}[(wel[c[1]], wel[c[2]], wel[c[3]]) for c in tris]
    newv = Dict{NTuple{2,Int},Int}()
    newv_pairs = NTuple{2,Int}[]       # welded endpoints of the first edge occurrence, in creation order
    newv_keys = NTuple{2,Int}[]
    tri_keys = Vector{NTuple{3,NTuple{2,Int}}}(undef, T)
    for k in 1:T
        c = tris[k]
        ks = ntuple(e -> begin
            p, q = e == 1 ? (c[1], c[2]) : e == 2 ? (c[2], c[3]) : (c[3], c[1])
            key = (min(p, q), max(p, q))
            if !haskey(newv, key)
                newv[key] = length(newv_keys) + 1
                push!(newv_keys, key)
                push!(newv_pairs, (wel[p], wel[q]))
            end
            key
        end, 3)
        tri_keys[k] = ks
    end
    nv_out, nt_out = n + length(newv_keys), 4T
    if nv_out > SHADER_MAX_VERTEXES || nt_out * 3 > SHADER_MAX_INDEXES
        return nothing, "too big ($nv_out verts, $nt_out tris)"
    end
    # edges of the welded mesh in first-seen order
    eidx = Dict{NTuple{2,Int},Int}()
    ekeys = NTuple{2,Int}[]
    elist = Vector{Vector{NTuple{4,Int}}}()  # (tri, opposite, u, v)
    for k in 1:T
        a, b, c = tt[k]
        for (u, v, opp) in ((a, b, c), (b, c, a), (c, a, b))
            u == v && continue
            key = u < v ? (u, v) : (v, u)
            i = get(eidx, key, 0)
            if i == 0
                push!(ekeys, key)
                push!(elist, NTuple{4,Int}[])
                i = length(ekeys)
                eidx[key] = i
            end
            push!(elist[i], (k, opp, u, v))
        end
    end
    fnu = Vector{V3}(undef, T)
    ln = Vector{Float64}(undef, T)
    for k in 1:T
        a, b, c = tt[k]
        fn = vcross(tp[b] - tp[a], tp[c] - tp[a])
        l = vnorm(fn)
        ln[k] = l
        fnu[k] = fn / max(l, 1e-12)
    end
    cos_c = cos(deg2rad(crease_angle))
    ecls = Vector{UInt8}(undef, length(ekeys))
    for (i, lst) in enumerate(elist)
        if length(lst) == 1
            ecls[i] = UInt8('B')
        elseif length(lst) > 2
            ecls[i] = UInt8('C')
        else
            (k1, _, u1, v1), (k2, _, u2, v2) = lst[1], lst[2]
            same = (u1 == u2 && v1 == v2)
            ecls[i] = (same || (ln[k1] > 1e-9 && ln[k2] > 1e-9 && vdot(fnu[k1], fnu[k2]) < cos_c)) ? UInt8('C') : UInt8('S')
        end
    end
    nb = [NTuple{2,Int}[] for _ in 1:nt_]   # (neighbour, class)
    for (i, (a, b)) in enumerate(ekeys)
        push!(nb[a], (b, Int(ecls[i])))
        push!(nb[b], (a, Int(ecls[i])))
    end
    vst = Vector{Union{Nothing,Vector{Pair{Int,Float64}}}}(undef, nt_)
    for t in 1:nt_
        cl = [x for x in nb[t] if x[2] == Int('C')]
        if any(x -> x[2] == Int('B'), nb[t]) || isempty(nb[t])
            vst[t] = nothing
        elseif length(cl) == 2
            vst[t] = [t => 0.75, cl[1][1] => 0.125, cl[2][1] => 0.125]
        elseif length(cl) != 0 || length(nb[t]) < 3
            vst[t] = nothing
        else
            m = length(nb[t])
            beta = m == 3 ? 3.0 / 16 : 3.0 / (8 * m)
            st = Pair{Int,Float64}[t => 1 - m * beta]
            for (o, _) in nb[t]
                push!(st, o => beta)
            end
            vst[t] = st
        end
    end
    acc = fill(ZERO3, nt_)
    for k in 1:T
        a, b, c = tt[k]
        cr = vcross(tp[b] - tp[a], tp[c] - tp[a])
        acc[a] = acc[a] + cr
        acc[b] = acc[b] + cr
        acc[c] = acc[c] + cr
    end
    sgn_sum = 0.0
    for i in 1:n
        sgn_sum += vdot(acc[wel[i]], N[i])
    end
    sign = sgn_sum < 0 ? -1.0 : 1.0
    tn = Vector{V3}(undef, nt_)
    for t in 1:nt_
        an = vnorm(acc[t])
        tn[t] = an > 1e-9 ? (sign * acc[t]) / max(an, 1e-12) : N[rep[t]]
    end
    proj(d::V3, nrm::V3) = vdot(d, nrm) * nrm
    ev = fill(ZERO3, nt_)
    for t in 1:nt_
        vst[t] === nothing && continue
        loop = ZERO3
        for (i, a) in vst[t]
            loop = loop + a * tp[i]
        end
        ev[t] = proj(loop - tp[t], tn[t])
    end
    no = length(newv_keys)
    Pn = Vector{V3}(undef, n + no)
    for i in 1:n
        Pn[i] = P[i] + ev[wel[i]]
    end
    for r in 1:no
        a_, b_ = newv_pairs[r]
        mid = 0.5 * (tp[a_] + tp[b_])
        ei = a_ == b_ ? 0 : get(eidx, (min(a_, b_), max(a_, b_)), 0)
        if ei != 0 && ecls[ei] == UInt8('S')
            opp = (elist[ei][1][2], elist[ei][2][2])
            ids = Int[]
            ws = Float64[]
            for (t_, c_) in ((a_, 0.375), (b_, 0.375), (opp[1], 0.125), (opp[2], 0.125))
                j = findfirst(==(t_), ids)
                if j === nothing
                    push!(ids, t_); push!(ws, c_)
                else
                    ws[j] += c_
                end
            end
            loop = ZERO3
            for (t_, w_) in zip(ids, ws)
                loop = loop + w_ * tp[t_]
            end
            on = tn[a_] + tn[b_]
            onl = vnorm(on)
            on = onl > 1e-3 ? on / max(onl, 1e-12) : ZERO3
            Pn[n+r] = mid + proj(loop - mid, on)
        else
            Pn[n+r] = mid
        end
    end
    Nn = Vector{V3}(undef, n + no)
    uvn = Vector{NTuple{2,Float64}}(undef, n + no)
    for i in 1:n
        Nn[i] = N[i]
        uvn[i] = uv[i]
    end
    for r in 1:no
        p, q = newv_keys[r]
        nn = N[p] + N[q]
        nl = vnorm(nn)
        Nn[n+r] = nl > 1e-6 ? nn / max(nl, 1e-12) : N[p]
        uvn[n+r] = ((uv[p][1] + uv[q][1]) * 0.5, (uv[p][2] + uv[q][2]) * 0.5)
    end
    ot = Vector{NTuple{3,Int}}(undef, 4T)
    for k in 1:T
        c0, c1, c2 = tris[k]
        m01, m12, m20 = (n + newv[tri_keys[k][e]] for e in 1:3)
        ot[4k-3] = (c0, m01, m20)
        ot[4k-2] = (c1, m12, m01)
        ot[4k-1] = (c2, m20, m12)
        ot[4k] = (m01, m12, m20)
    end
    SmoothResult(Pn, Nn, uvn, ot, newv_keys, T, nt_out), ""
end

dv_pos(v::DrawVert) = V3(Float64(v.x), Float64(v.y), Float64(v.z))
dv_nrm(v::DrawVert) = V3(Float64(v.nx), Float64(v.ny), Float64(v.nz))

"Smoothed vertex array: positions/normals/uv from the smoother, lm/colour averaged for the new vertices."
function smoothed_verts(av::AbstractVector{DrawVert}, res::SmoothResult)
    n0 = length(av)
    out = Vector{DrawVert}(undef, length(res.Pn))
    for i in 1:length(res.Pn)
        p, nn, uv = res.Pn[i], res.Nn[i], res.uvn[i]
        if i <= n0
            o = av[i]
            l1, l2, c1, c2, c3, c4 = o.l1, o.l2, o.c1, o.c2, o.c3, o.c4
        else
            a, b = av[res.pv[i-n0][1]], av[res.pv[i-n0][2]]
            l1 = (a.l1 + b.l1) * 0.5f0
            l2 = (a.l2 + b.l2) * 0.5f0
            c1 = UInt8((Int32(a.c1) + Int32(b.c1)) ÷ 2)
            c2 = UInt8((Int32(a.c2) + Int32(b.c2)) ÷ 2)
            c3 = UInt8((Int32(a.c3) + Int32(b.c3)) ÷ 2)
            c4 = UInt8((Int32(a.c4) + Int32(b.c4)) ÷ 2)
        end
        out[i] = DrawVert(Float32(p.x), Float32(p.y), Float32(p.z), Float32(uv[1]), Float32(uv[2]), l1, l2,
                          Float32(nn.x), Float32(nn.y), Float32(nn.z), c1, c2, c3, c4)
    end
    out
end

"Lay the vertex/index lumps out again: every surface's own range in surface order; `mods` replaces ranges."
function relayout(bsp::Bsp, S::Vector{Surface}, V0::Vector{DrawVert}, I0::Vector{Int32}, mods::Dict{Int,Tuple{Vector{DrawVert},Vector{Int32}}})
    newv = DrawVert[]
    newi = Int32[]
    S2 = similar(S)
    for si in 1:length(S)
        s = S[si]
        if haskey(mods, si - 1)
            av, ai = mods[si-1]
        else
            av = view(V0, s.fv+1:s.fv+s.nv)
            ai = view(I0, s.fi+1:s.fi+s.ni)
        end
        S2[si] = with_geometry(s; fv=length(newv), nv=length(av), fi=length(newi), ni=length(ai))
        append!(newv, av)
        append!(newi, ai)
    end
    replace_lumps(bsp, newv, newi, S2), length(newv), length(newi)
end

const DEFAULT_SMOOTH = r"^models[/\\](?!players)|textures/(props|metal_misc|wood|chat)/"
const DEFAULT_BRUSH_PROPS = r"textures/(props|metal_misc|wood|town_wood|chat)/"

function smooth_trisoup(bsp::Bsp, rx::Regex; crease=90.0, quiet=false)
    V0, I0, S = verts(bsp), indexes(bsp), surfaces(bsp)
    names = shader_names(bsp)
    mods = Dict{Int,Tuple{Vector{DrawVert},Vector{Int32}}}()
    st = Dict{String,Int}()
    inc(k, v=1) = (st[k] = get(st, k, 0) + v)
    for si in 1:length(S)
        s = S[si]
        s.typ == MST_TRISOUP && s.ni >= 24 || continue
        occursin(rx, names[s.shader+1]) || continue
        av = V0[s.fv+1:s.fv+s.nv]
        ai = I0[s.fi+1:s.fi+s.ni]
        tris = NTuple{3,Int}[(Int(ai[3k-2]) + 1, Int(ai[3k-1]) + 1, Int(ai[3k]) + 1) for k in 1:length(ai)÷3]
        res, why = smooth_surface(dv_pos.(av), dv_nrm.(av), tris, NTuple{2,Float64}[(Float64(v.s), Float64(v.t)) for v in av]; crease_angle=crease)
        if res === nothing
            inc("skipped: " * (split(why, " (")[1]))
        else
            ot = Int32[Int32(x - 1) for t in res.ot for x in t]
            mods[si-1] = (smoothed_verts(av, res), ot)
            inc("smoothed"); inc("tris_before", res.before_t); inc("tris_after", res.after_t)
        end
    end
    quiet || println("baked models: ", sort!(collect(st)))
    out, _, _ = relayout(bsp, S, V0, I0, mods)
    out
end

function smooth_brush_props(bsp::Bsp; rx=DEFAULT_BRUSH_PROPS, max_extent=100.0, min_faces=6, crease=90.0, quiet=false)
    V0, I0, S = verts(bsp), indexes(bsp), surfaces(bsp)
    names = shader_names(bsp)
    m0 = models(bsp)[1]
    cand = Int[si for si in m0.fs:m0.fs+m0.ns-1 if S[si+1].typ == MST_PLANAR && S[si+1].fog <= 0 && occursin(rx, names[S[si+1].shader+1])]
    par = Dict{Int,Int}(si => si for si in cand)
    function find(x)
        while par[x] != x
            par[x] = par[par[x]]
            x = par[x]
        end
        x
    end
    owner = Dict{NTuple{3,Int64},Int}()
    for si in cand
        s = S[si+1]
        for v in view(V0, s.fv+1:s.fv+s.nv)
            k = (round(Int64, Float64(v.x) * 8), round(Int64, Float64(v.y) * 8), round(Int64, Float64(v.z) * 8))
            o = get(owner, k, nothing)
            if o !== nothing
                par[find(si)] = find(o)
            else
                owner[k] = si
            end
        end
    end
    comps = Dict{Int,Vector{Int}}()
    comp_order = Int[]
    for si in cand
        r = find(si)
        if !haskey(comps, r)
            comps[r] = Int[]
            push!(comp_order, r)
        end
        push!(comps[r], si)
    end
    mods = Dict{Int,Tuple{Vector{DrawVert},Vector{Int32}}}()
    st = Dict{String,Int}()
    inc(k, v=1) = (st[k] = get(st, k, 0) + v)
    for r in comp_order
        sis = sort(comps[r])
        mn = [Inf32, Inf32, Inf32]; mx = [-Inf32, -Inf32, -Inf32]
        for i in sis
            s = S[i+1]
            for v in view(V0, s.fv+1:s.fv+s.nv)
                mn[1] = min(mn[1], v.x); mn[2] = min(mn[2], v.y); mn[3] = min(mn[3], v.z)
                mx[1] = max(mx[1], v.x); mx[2] = max(mx[2], v.y); mx[3] = max(mx[3], v.z)
            end
        end
        if length(sis) < min_faces || maximum(mx .- mn) > max_extent
            inc("components skipped")
            continue
        end
        av = DrawVert[]
        tris = NTuple{3,Int}[]
        tsurf = Int[]
        for i in sis
            s = S[i+1]
            base = length(av)
            append!(av, view(V0, s.fv+1:s.fv+s.nv))
            for k in 1:s.ni÷3
                push!(tris, (Int(I0[s.fi+3k-2]) + 1 + base, Int(I0[s.fi+3k-1]) + 1 + base, Int(I0[s.fi+3k]) + 1 + base))
                push!(tsurf, i)
            end
        end
        res, _ = smooth_surface(dv_pos.(av), dv_nrm.(av), tris, NTuple{2,Float64}[(Float64(v.s), Float64(v.t)) for v in av]; crease_angle=crease)
        if res === nothing
            inc("components too big")
            continue
        end
        bv = smoothed_verts(av, res)
        ok = true
        out = Dict{Int,Tuple{Vector{DrawVert},Vector{Int32}}}()
        for i in sis
            sel = NTuple{3,Int}[]
            for k in 1:length(tris)
                tsurf[k] == i || continue
                for q in 4k-3:4k
                    push!(sel, res.ot[q])
                end
            end
            used = sort!(unique!(Int[x for t in sel for x in t]))
            if length(used) > MAX_BEVEL_FACE_VERTS
                ok = false
                break
            end
            pos = Dict{Int,Int}(u => j - 1 for (j, u) in enumerate(used))
            out[i] = (bv[used], Int32[Int32(pos[x]) for t in sel for x in t])
        end
        if !ok
            inc("components over vertex limit")
            continue
        end
        merge!(mods, out)
        inc("components smoothed"); inc("surfaces", length(sis))
    end
    quiet || println("brush props: ", sort!(collect(st)))
    out, _, _ = relayout(bsp, S, V0, I0, mods)
    out
end
