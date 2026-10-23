# World bevel, part 2: run preparation, box corners, wall ends, mitres, overlap rejection, texture alignment.

function layout!(bv::Bevel, gr::Group)
    a, r = bv.a, gr.r
    L = gr.hi - gr.lo
    gr.tap = min(a.taper === nothing ? 2r : a.taper, L / 3)
    cl, ch = gr.corner[1], gr.corner[2]
    gr.te_lo = cl ? (isnan(gr.corner_te[1]) ? gr.lo + r : gr.corner_te[1]) : gr.lo
    gr.te_hi = ch ? (isnan(gr.corner_te[2]) ? gr.hi - r : gr.corner_te[2]) : gr.hi
    fl = cl || gr.wall[1] || gr.mitre[1] !== nothing
    fh = ch || gr.wall[2] || gr.mitre[2] !== nothing
    bps = Float64[gr.lo]
    cv = Float64[fl ? r : 0.0]
    if !fl
        push!(bps, gr.lo + gr.tap); push!(cv, r)
    end
    if !fh
        push!(bps, gr.hi - gr.tap); push!(cv, r)
    end
    push!(bps, gr.hi); push!(cv, fh ? r : 0.0)
    gr.bps = Float64[bps[1]]
    gr.cvals = Float64[cv[1]]
    for k in 2:length(bps)
        if bps[k] - gr.bps[end] > 1e-6
            push!(gr.bps, bps[k]); push!(gr.cvals, cv[k])
        end
    end
end

function c_at(gr::Group, t::Float64)
    bps, cv = gr.bps, gr.cvals
    t <= bps[1] && return cv[1]
    t >= bps[end] && return cv[end]
    for k in 1:length(bps)-1
        if bps[k] <= t <= bps[k+1]
            return cv[k] + (cv[k+1] - cv[k]) * (t - bps[k]) / (bps[k+1] - bps[k])
        end
    end
    0.0
end

# --- 5. group checks -----------------------------------------------------------------------------------------------
function prepare!(bv::Bevel, gr::Group)::Union{Nothing,String}
    a = bv.a
    gr.hi - gr.lo < a.min_length && return "rej_short"
    cA = ZERO3
    for s in gr.fA.keys
        cA = cA + face(bv, s).centroid
    end
    cA = cA / length(gr.fA)
    cB = ZERO3
    for s in gr.fB.keys
        cB = cB + face(bv, s).centroid
    end
    cB = cB / length(gr.fB)
    gr.wA = unit(vcross(gr.d, gr.nA))
    vdot(gr.wA, cA - gr.P0) < 0 && (gr.wA = -gr.wA)
    gr.wB = unit(vcross(gr.d, gr.nB))
    vdot(gr.wB, cB - gr.P0) < 0 && (gr.wB = -gr.wB)
    if !(vdot(gr.nA, gr.wB) < -1e-3 && vdot(gr.nB, gr.wA) < -1e-3)
        return "rej_concave_group"
    end
    dmin = 1e18
    for (store, w) in ((gr.fA, gr.wA), (gr.fB, gr.wB))
        for s in store.keys
            f = face(bv, s)
            m = -Inf
            for q in f.A
                m = max(m, vdot(axyz(q) - gr.P0, w))
            end
            dmin = min(dmin, m)
        end
    end
    gr.r = min(a.radius, 0.45 * dmin)
    gr.r < a.min_radius - 1e-9 && return "rej_thin_face"
    gr.theta = acos(max(-1.0, min(1.0, vdot(gr.nA, gr.nB))))
    gr.R_over_c = 1.0 / tan(gr.theta / 2)
    layout!(bv, gr)
    nothing
end

# --- 5b. box corners ------------------------------------------------------------------------------------------------
cell3(p::V3) = (floor(Int, p.x / 2), floor(Int, p.y / 2), floor(Int, p.z / 2))

function near_ends(grid, ends, p::V3)
    c0 = cell3(p)
    near = Int[]
    for dx in -1:1, dy in -1:1, dz in -1:1
        lst = get(grid, (c0[1] + dx, c0[2] + dy, c0[3] + dz), nothing)
        lst === nothing && continue
        for j in lst
            vnorm(ends[j][3] - p) < 0.75 && push!(near, j)
        end
    end
    near
end

function find_corners!(bv::Bevel, order::Vector{Int})
    ends = Tuple{Int,Int,V3}[]
    for gid in order
        gr = bv.groups[gid]
        if gr.hi - gr.lo >= 2 * gr.r + 1.0
            push!(ends, (gid, 0, gr.P0 + gr.d * gr.lo))
            push!(ends, (gid, 1, gr.P0 + gr.d * gr.hi))
        end
    end
    grid = Dict{NTuple{3,Int},Vector{Int}}()
    for (k, (_g, _e, p)) in enumerate(ends)
        push!(get!(grid, cell3(p), Int[]), k)
    end
    normals = Dict{Int,V3}()
    for gid in order
        gr = bv.groups[gid]
        normals[gr.pk[1]] = gr.nA
        normals[gr.pk[2]] = gr.nB
    end
    bv.corners = Corner[]
    seen = Set{Int}()
    for (k, (_g, _e, p)) in enumerate(ends)
        k in seen && continue
        near = near_ends(grid, ends, p)
        union!(seen, near)
        length(near) < 3 && continue
        if length(near) != 3
            inc!(bv, "corner_rej_not_three_runs"); continue
        end
        gids = [ends[j][1] for j in near]
        pks = [bv.groups[g].pk for g in gids]
        planes = Set(x for pk in pks for x in pk)
        if length(Set(gids)) != 3 || length(planes) != 3 || length(Set(pks)) != 3
            inc!(bv, "corner_rej_not_a_box_vertex"); continue
        end
        ok = true
        for j in near
            gr = bv.groups[ends[j][1]]
            third = first(setdiff(planes, Set(gr.pk)))
            n3 = normals[third]
            u = ends[j][2] == 0 ? gr.d : -gr.d
            vdot(u, n3) > -0.985 && (ok = false)
        end
        if !ok
            inc!(bv, "corner_rej_not_orthogonal"); continue
        end
        pos = ZERO3
        for j in near
            pos = pos + ends[j][3]
        end
        push!(bv.corners, Corner([(ends[j][1], ends[j][2]) for j in near], pos / 3, sort!(collect(planes))))
    end
    changed = true
    while changed
        changed = false
        for cr in bv.corners
            rc = minimum(bv.groups[g].r for (g, _e) in cr.ends)
            for (g, _e) in cr.ends
                if bv.groups[g].r > rc + 1e-9
                    bv.groups[g].r = rc
                    changed = true
                end
            end
        end
    end
    good = Corner[]
    for cr in bv.corners
        te = corner_extents(bv, cr)
        if te === nothing
            inc!(bv, "corner_rej_skewed"); continue
        end
        for ((g, e), t) in zip(cr.ends, te)
            bv.groups[g].corner[e+1] = true
            bv.groups[g].corner_te[e+1] = t
        end
        push!(good, cr)
    end
    bv.corners = good
    for gid in order
        layout!(bv, bv.groups[gid])
    end
    bv.stats["corners_found"] = length(bv.corners)
end

function corner_extents(bv::Bevel, cr::Corner)::Union{Nothing,Vector{Float64}}
    per = Dict{Tuple{Int,Int},Vector{Float64}}()
    for plane in cr.planes
        hits = [(g, e) for (g, e) in cr.ends if plane in bv.groups[g].pk]
        length(hits) != 2 && return nothing
        rows = V3[]
        rhs = Float64[]
        fc = nothing
        for (g, e) in hits
            gr = bv.groups[g]
            side_a = gr.pk[1] == plane
            w, store = side_a ? (gr.wA, gr.fA) : (gr.wB, gr.fB)
            fc = face(bv, store.keys[1])
            push!(rows, w)
            push!(rhs, gr.r + vdot(w, gr.P0))
        end
        push!(rows, fc.n)
        push!(rhs, fc.d)
        X = solve3((rows[1], rows[2], rows[3]), (rhs[1], rhs[2], rhs[3]))
        X === nothing && return nothing
        for (g, e) in hits
            gr = bv.groups[g]
            push!(get!(per, (g, e), Float64[]), vdot(X - gr.P0, gr.d))
        end
    end
    out = Float64[]
    for (g, e) in cr.ends
        v = get(per, (g, e), Float64[])
        (length(v) != 2 || abs(v[1] - v[2]) > 0.05) && return nothing
        t = 0.5 * (v[1] + v[2])
        gr = bv.groups[g]
        (abs(t - (e == 0 ? gr.lo + gr.r : gr.hi - gr.r)) > 0.5 * gr.r || !(gr.lo < t < gr.hi)) && return nothing
        push!(out, t)
    end
    out
end

function revert_broken_corners!(bv::Bevel)
    keep = Corner[]
    for cr in bv.corners
        if all(bv.groups[g].ok for (g, _e) in cr.ends)
            push!(keep, cr)
            continue
        end
        inc!(bv, "corners_reverted")
        for (g, e) in cr.ends
            gr = bv.groups[g]
            if gr.ok
                gr.corner[e+1] = false
                layout!(bv, gr)
            end
        end
    end
    bv.corners = keep
end

# rebuild_cutverts: every vertex of the final clipped faces that lies on a run's cut line becomes a strip row
function rebuild_cutverts!(bv::Bevel)
    for (gid, gr) in enumerate(bv.groups)
        gr.ok || continue
        for (store, w) in ((gr.fA, gr.wA), (gr.fB, gr.wB))
            for sid in store.keys
                f = face(bv, sid)
                for P in f.polys
                    for q in P
                        x = axyz(q)
                        tp = vdot(x - gr.P0, gr.d)
                        if gr.lo - 1e-6 <= tp <= gr.hi + 1e-6
                            sp = vdot(x - gr.P0, w)
                            if abs(sp - c_at(gr, tp)) < 1e-6
                                push!(f.cutverts, CutVert(gid, tp, x))
                            end
                        end
                    end
                end
            end
        end
    end
end

# --- 5c. wall ends ---------------------------------------------------------------------------------------------------
"Is pt (projected on the plane of face f) inside one of its triangles (tolerance tol units)?"
function point_in_face(f::Face, pt::V3, tol::Float64=0.1)
    pu, pv = vdot(pt, f.u), vdot(pt, f.v)
    A = f.A
    @inbounds for t in f.tris
        a, b, c = A[t[1]], A[t[2]], A[t[3]]
        a0x = a[1] * f.u.x + a[2] * f.u.y + a[3] * f.u.z
        a0y = a[1] * f.v.x + a[2] * f.v.y + a[3] * f.v.z
        e1x = (b[1] * f.u.x + b[2] * f.u.y + b[3] * f.u.z) - a0x
        e1y = (b[1] * f.v.x + b[2] * f.v.y + b[3] * f.v.z) - a0y
        e2x = (c[1] * f.u.x + c[2] * f.u.y + c[3] * f.u.z) - a0x
        e2y = (c[1] * f.v.x + c[2] * f.v.y + c[3] * f.v.z) - a0y
        det = e1x * e2y - e1y * e2x
        dpx = pu - a0x
        dpy = pv - a0y
        a_ = (dpx * e2y - dpy * e2x) / det
        b_ = (e1x * dpy - e1y * dpx) / det
        e = tol / max(sqrt(abs(det)), 1e-6)
        if a_ >= -e && b_ >= -e && a_ + b_ <= 1 + 2e && abs(det) > 1e-9
            return true
        end
    end
    false
end

function near_edge(pt::V3, P0s::Vector{V3}, P1s::Vector{V3}, idx::Vector{Int})
    best = Inf
    for k in idx
        a, b = P0s[k], P1s[k]
        ab = b - a
        tt = min(max(vdot(pt - a, ab) / max(vdot(ab, ab), 1e-12), 0.0), 1.0)
        best = min(best, vnorm(a + tt * ab - pt))
    end
    best
end

function find_wall_ends!(bv::Bevel, order::Vector{Int})
    empty!(bv.wall_why)
    bv.a.wall_ends || return
    a = bv.a
    fl = [f for f in bv.flist if !f.bad]
    nf = length(fl)
    FN = V3[f.n for f in fl]
    FD = Float64[f.d for f in fl]
    byface = Dict{Int,Vector{Int}}()
    for (k, si) in enumerate(bv.Ef)
        push!(get!(byface, si, Int[]), k)
    end
    for gid in order
        gr = bv.groups[gid]
        for e in (0, 1)
            gr.corner[e+1] && continue
            t = e == 0 ? gr.lo : gr.hi
            u = e == 0 ? gr.d : -gr.d
            p = gr.P0 + gr.d * t
            m = Int[i for i in 1:nf if vdot(FN[i], u) >= a.wall_dot && abs(vdot(FN[i], p) - FD[i]) < 0.3]
            if isempty(m)
                inc!(bv, "wall_rej_no_plane")
                bv.wall_why[(gid, e)] = "no_plane"
                continue
            end
            idx = Int[k for i in m for k in get(byface, fl[i].si, Int[])]
            if isempty(idx)
                inc!(bv, "wall_rej_no_hole"); continue
            end
            wf = Face[fl[i] for i in m]
            diag = (gr.wA + gr.wB) * gr.r
            cov = [any(f -> point_in_face(f, p + diag * k), wf) for k in (0.08, 0.2)]
            if all(cov)
                gr.wall_cap[e+1] = false
                inc!(bv, "wall_ends_under")
            else
                ok = !any(cov) && near_edge(p, bv.Ep0, bv.Ep1, idx) < 0.25
                for w in (gr.wA, gr.wB)
                    for fr in (0.5, 1.0)
                        ok = ok && near_edge(p + w * gr.r * fr, bv.Ep0, bv.Ep1, idx) < 0.25
                    end
                end
                if !ok
                    inc!(bv, "wall_rej_no_hole")
                    bv.wall_why[(gid, e)] = "no_hole"
                    continue
                end
            end
            gr.wall[e+1] = true
            gr.wall_fi[e+1] = Int[fl[i].si for i in m]
            best = m[1]
            bd = vdot(FN[m[1]], u)
            for i in m[2:end]
                dd = vdot(FN[i], u)
                if dd > bd
                    bd = dd; best = i
                end
            end
            gr.wall_pl[e+1] = (FN[best], FD[best])
            inc!(bv, "wall_ends")
        end
    end
    for gid in order
        layout!(bv, bv.groups[gid])
    end
end

# --- 5d. mitres ----------------------------------------------------------------------------------------------------
function drop_ext!(bv::Bevel, gr::Group, e::Int)
    m = gr.mitre[e+1]
    for sid in m.added
        store_pop!(gr.pk[1] == m.P ? gr.fA : gr.fB, sid)
    end
    gr.mitre[e+1] = nothing
    layout!(bv, gr)
end

function clear_mitre!(bv::Bevel, gr::Group, e::Int)
    g2, e2 = gr.mitre[e+1].partner
    p = bv.groups[g2]
    drop_ext!(bv, gr, e)
    p.mitre[e2+1] !== nothing && drop_ext!(bv, p, e2)
end

function extend_store!(bv::Bevel, gr::Group, e::Int)
    m = gr.mitre[e+1]
    p_first = gr.pk[1] == m.P
    store, w = p_first ? (gr.fA, gr.wA) : (gr.fB, gr.wB)
    f0 = face(bv, store.keys[1])
    u = e == 0 ? gr.d : -gr.d
    r = gr.r
    pts = V3[m.V - u * r * a_ + w * r * b_ for a_ in (0.1, 0.5, 0.9) for b_ in (0.1, 0.5, 0.9)]
    m.added = Int[]
    for f in bv.flist
        (f.si in store || f.bad || abs(vdot(f.n, f0.n) - 1) > 1e-4 || abs(f.d - f0.d) > 0.1) && continue
        if any(x -> point_in_face(f, x), pts)
            store_widen!(store, f.si, e == 0 ? gr.lo - r : gr.hi, e == 0 ? gr.lo : gr.hi + r)
            push!(m.added, f.si)
        end
    end
end

function find_mitres!(bv::Bevel, order::Vector{Int})
    empty!(bv.mitres)
    bv.a.mitre || return
    ends = Tuple{Int,Int,V3}[]
    for gid in order
        gr = bv.groups[gid]
        gr.hi - gr.lo < 2 * gr.r + 1.0 && continue
        for e in (0, 1)
            if !(gr.corner[e+1] || gr.wall[e+1])
                push!(ends, (gid, e, gr.P0 + gr.d * (e == 0 ? gr.lo : gr.hi)))
            end
        end
    end
    grid = Dict{NTuple{3,Int},Vector{Int}}()
    for (k, (_g, _e, p)) in enumerate(ends)
        push!(get!(grid, cell3(p), Int[]), k)
    end
    seen = Set{Int}()
    for (k, (_g, _e, p)) in enumerate(ends)
        k in seen && continue
        near = near_ends(grid, ends, p)
        union!(seen, near)
        (length(near) != 2 || ends[near[1]][1] == ends[near[2]][1]) && continue
        (g1, e1, p1), (g2, e2, p2) = ends[near[1]], ends[near[2]]
        r1, r2 = bv.groups[g1], bv.groups[g2]
        common = intersect(Set(r1.pk), Set(r2.pk))
        inc!(bv, "mitre_cand")
        if length(common) != 1
            inc!(bv, "mitre_rej_planes"); continue
        end
        P = first(common)
        if abs(r1.r - r2.r) > 1e-6 || abs(vdot(r1.nA, r1.nB) - vdot(r2.nA, r2.nB)) > 1e-3
            inc!(bv, "mitre_rej_radius_angle"); continue
        end
        u1 = e1 == 0 ? r1.d : -r1.d
        u2 = e2 == 0 ? r2.d : -r2.d
        w1 = r1.pk[1] == P ? r1.wA : r1.wB
        w2 = r2.pk[1] == P ? r2.wA : r2.wB
        if abs(vdot(u1, u2)) > 0.02 || vdot(-u1, w2) < 0.98 || vdot(-u2, w1) < 0.98
            inc!(bv, "mitre_rej_not_reflex_L"); continue
        end
        sh = SharedPts(nothing)
        V = 0.5 * (p1 + p2)
        nPi = unit(u2 - u1)
        r1.mitre[e1+1] = Mitre((g2, e2), P, V, nPi, sh, Int[])
        r2.mitre[e2+1] = Mitre((g1, e1), P, V, nPi, sh, Int[])
        extend_store!(bv, r1, e1)
        extend_store!(bv, r2, e2)
        push!(bv.mitres, (g1, e1, g2, e2))
        inc!(bv, "mitres_found")
    end
    for gid in order
        layout!(bv, bv.groups[gid])
    end
end

function revert_broken_mitres!(bv::Bevel)
    for (g1, e1, g2, e2) in bv.mitres
        a_, b_ = bv.groups[g1], bv.groups[g2]
        (a_.ok && b_.ok) && continue
        for (gr, e) in ((a_, e1), (b_, e2))
            gr.mitre[e+1] !== nothing && drop_ext!(bv, gr, e)
        end
        inc!(bv, "mitres_reverted_partner")
    end
end

# --- overlap / coverage rejection -----------------------------------------------------------------------------------
function mext(gr::Group, side::Int)
    ntuple(e -> (gr.mitre[e] !== nothing && gr.mitre[e].P == gr.pk[side+1]) ? gr.r : 0.0, 2)
end

const P2 = NTuple{2,Float64}

function region(gr::Group, f::Face, w::V3, side::Int)::Vector{P2}
    r, tap = gr.r, gr.tap
    x0, x1 = mext(gr, side)
    lo0 = (gr.corner[1] || gr.wall[1]) ? [(gr.te_lo, 0.0), (gr.te_lo, r)] : [(gr.lo, 0.0), (gr.lo + tap, r)]
    hi0 = (gr.corner[2] || gr.wall[2]) ? [(gr.te_hi, 0.0), (gr.te_hi, r)] : [(gr.hi, 0.0), (gr.hi - tap, r)]
    gr.mitre[1] !== nothing && (lo0 = [(gr.lo - x0, 0.0), (gr.lo - x0, r)])
    gr.mitre[2] !== nothing && (hi0 = [(gr.hi + x1, 0.0), (gr.hi + x1, r)])
    pts = (lo0[1], hi0[1], hi0[2], lo0[2])
    P2[(x = gr.P0 + gr.d * t + w * s_; (vdot(x, f.u), vdot(x, f.v))) for (t, s_) in pts]
end

function poly_overlap(A::Vector{P2}, B::Vector{P2})
    for poly in (A, B)
        n = length(poly)
        for i in 1:n
            q = poly[i%n+1]
            e = (q[1] - poly[i][1], q[2] - poly[i][2])
            nx, ny = -e[2], e[1]
            nl = sqrt(nx * nx + ny * ny)
            nl < 1e-9 && continue
            nx /= nl; ny /= nl
            a0 = Inf; a1 = -Inf; b0 = Inf; b1 = -Inf
            for p in A
                v = p[1] * nx + p[2] * ny
                a0 = min(a0, v); a1 = max(a1, v)
            end
            for p in B
                v = p[1] * nx + p[2] * ny
                b0 = min(b0, v); b1 = max(b1, v)
            end
            min(a1, b1) - max(a0, b0) < 0.05 && return false
        end
    end
    true
end

function covered(bv::Bevel, gr::Group, store::Store, w::V3, side::Int)
    r = gr.r
    tl = (gr.corner[1] || gr.wall[1] || gr.mitre[1] !== nothing) ? 0.0 : gr.tap
    th = (gr.corner[2] || gr.wall[2] || gr.mitre[2] !== nothing) ? 0.0 : gr.tap
    e = min(0.3, 0.25 * (gr.te_hi - gr.te_lo))
    q = Tuple{Float64,Float64}[(gr.te_lo + e, 0.1), (gr.te_hi - e, 0.1), (gr.te_lo + max(tl, e), r - 0.1), (gr.te_hi - max(th, e), r - 0.1),
                               (0.5 * (gr.lo + gr.hi), 0.1), (0.5 * (gr.lo + gr.hi), r - 0.1),
                               (gr.te_lo + max(0.5 * tl, e), 0.5 * r), (gr.te_hi - max(0.5 * th, e), 0.5 * r)]
    x0, x1 = mext(gr, side)
    if x0 > 0
        append!(q, [(gr.lo - 0.5 * x0, 0.1), (gr.lo - 0.5 * x0, r - 0.1), (gr.lo - x0 + 0.2, 0.2), (gr.lo - x0 + 0.2, r - 0.1)])
    end
    if x1 > 0
        append!(q, [(gr.hi + 0.5 * x1, 0.1), (gr.hi + 0.5 * x1, r - 0.1), (gr.hi + x1 - 0.2, 0.2), (gr.hi + x1 - 0.2, r - 0.1)])
    end
    for (t, s_) in q
        pt = gr.P0 + gr.d * t + w * s_
        ok = false
        for sid in store.keys
            if point_in_face(face(bv, sid), pt)
                ok = true
                break
            end
        end
        ok || return false
    end
    true
end

"""
Rounding a convex edge removes a wedge of solid at its tip. If another surface (not on the run's two faces, not coplanar
with them) has a vertex sitting on the edge line strictly inside the run, e.g. a plinth or stair block touching the
corner, grazing views through the wedge reach a spot with no drawn surface and show the clear colour (white holes).
Leave such runs un-bevelled.
"""
function reject_touched_edges!(bv::Bevel, order::Vector{Int})
    ps = V3[]; ns = V3[]; sf = Int[]
    for (si, sr) in enumerate(bv.S)
        sr.typ == MST_PLANAR || continue
        for k in 0:sr.nv-1
            v = bv.V[sr.fv+k+1]
            push!(ps, V3(v.x, v.y, v.z)); push!(ns, V3(v.nx, v.ny, v.nz)); push!(sf, si - 1)
        end
    end
    for gid in order
        gr = bv.groups[gid]
        gr.ok || continue
        len = gr.hi - gr.lo
        len > 2 * gr.r || continue
        m = 0.25 + 0.0 * gr.r
        hit = false
        for i in eachindex(ps)
            w = ps[i] - gr.P0
            t = vdot(w, gr.d)
            (t > gr.lo + 0.5 && t < gr.hi - 0.5) || continue
            q = w - t * gr.d
            vdot(q, q) <= m * m || continue
            (sf[i] in gr.fA || sf[i] in gr.fB) && continue
            n = ns[i]
            # a surface continuing one of the run's planes (same facing) is just part of that wall; an opposite-facing one
            # means a second solid touches the edge (diagonal contact), so it counts
            (vdot(n, gr.nA) > 0.99 || vdot(n, gr.nB) > 0.99) && continue
            hit = true
            break
        end
        if hit
            gr.ok = false
            inc!(bv, "rej_touched_edge")
        end
    end
    # Two solids touching along the same edge line (diagonal contact, a checkerboard in plan): rounding either one opens
    # a slit between them. Reject every run that shares its line and an overlapping range with a run of other faces.
    lines = Dict{NTuple{6,Int},Vector{Int}}()
    for gid in order
        gr = bv.groups[gid]
        gr.ok || continue
        d = gr.d
        sg = (d.x != 0 ? d.x : d.y != 0 ? d.y : d.z) < 0 ? -1.0 : 1.0
        d = d * sg
        q = gr.P0 - gr.d * vdot(gr.P0, gr.d)
        key = (round(Int, q.x * 4), round(Int, q.y * 4), round(Int, q.z * 4), round(Int, d.x * 64), round(Int, d.y * 64), round(Int, d.z * 64))
        push!(get!(Vector{Int}, lines, key), gid)
    end
    for ids in values(lines)
        length(ids) > 1 || continue
        drop = Int[]
        for (i, a) in enumerate(ids), b in ids[i+1:end]
            ga, gb = bv.groups[a], bv.groups[b]
            isempty(intersect(ga.fA.keys, gb.fA.keys)) && isempty(intersect(ga.fA.keys, gb.fB.keys)) &&
                isempty(intersect(ga.fB.keys, gb.fA.keys)) && isempty(intersect(ga.fB.keys, gb.fB.keys)) || continue
            # ranges along the shared direction
            ta0, ta1 = sort([vdot(ga.P0 + ga.d * ga.lo, ga.d), vdot(ga.P0 + ga.d * ga.hi, ga.d)])
            tb0, tb1 = sort([vdot(gb.P0 + gb.d * gb.lo, ga.d), vdot(gb.P0 + gb.d * gb.hi, ga.d)])
            min(ta1, tb1) - max(ta0, tb0) > 1.0 || continue
            # diagonal contact: the solids sit in opposite quadrants, i.e. each run's open side faces the other's solid
            vdot(ga.nA + ga.nB, gb.nA + gb.nB) < -0.5 || continue
            push!(drop, a, b)
        end
        for g in unique(drop)
            bv.groups[g].ok = false
            inc!(bv, "rej_diagonal_contact")
        end
    end
    # Box vertex whose third edge (e.g. a low step riser) was not bevelled: a mitre of the two other edges leaves a
    # hole at the vertex, so revert those mitres to plain tapers.
    for gid in order
        gr = bv.groups[gid]
        gr.ok || continue
        for e in (0, 1)
            m = gr.mitre[e+1]
            m === nothing && continue
            pg = bv.groups[m.partner[1]]
            # the two non-shared face normals
            shared = abs(vdot(gr.nB, pg.nB)) > 0.99 || abs(vdot(gr.nB, pg.nA)) > 0.99 ? gr.nB : gr.nA
            n1 = shared === gr.nB ? gr.nA : gr.nB
            n2 = abs(vdot(shared, pg.nA)) > 0.99 ? pg.nB : pg.nA
            abs(vdot(n1, n2)) < 0.1 || continue
            t3 = vcross(n1, n2); t3 = t3 / sqrt(vdot(t3, t3))
            pe = gr.P0 + gr.d * (e == 0 ? gr.lo : gr.hi)
            found = false
            for g3 in bv.groups
                g3.ok && abs(abs(vdot(g3.d, t3)) - 1) < 1e-3 || continue
                w = pe - g3.P0
                t = vdot(w, g3.d)
                q = w - t * g3.d
                (vdot(q, q) < 0.09 && t > g3.lo - 0.3 && t < g3.hi + 0.3) && (found = true; break)
            end
            if !found
                clear_mitre!(bv, gr, e)
                inc!(bv, "mitre_reverted_box_vertex")
            end
        end
    end
end

function drop_overlapping!(bv::Bevel, order::Vector{Int})
    placed = Dict{Int,Vector{Tuple{Vector{P2},Int}}}()
    for gid in sort(order, by=g -> -(bv.groups[g].hi - bv.groups[g].lo), alg=MergeSort)
        gr = bv.groups[gid]
        for e in (0, 1)
            if gr.mitre[e+1] !== nothing && !bv.groups[gr.mitre[e+1].partner[1]].ok
                clear_mitre!(bv, gr, e)
            end
        end
        bad = ""
        mine = Tuple{Int,Vector{P2}}[]
        for attempt in (0, 1)
            bad = ""
            partners = Set(m.partner[1] for m in gr.mitre if m !== nothing)
            if !(covered(bv, gr, gr.fA, gr.wA, 0) && covered(bv, gr, gr.fB, gr.wB, 1))
                bad = "rej_face_coverage"
            else
                mine = Tuple{Int,Vector{P2}}[(s, region(gr, face(bv, s), gr.wA, 0)) for s in gr.fA.keys]
                append!(mine, Tuple{Int,Vector{P2}}[(s, region(gr, face(bv, s), gr.wB, 1)) for s in gr.fB.keys])
                hit = false
                for (s, poly) in mine
                    for (q, g2) in get(placed, s, Tuple{Vector{P2},Int}[])
                        if !(g2 in partners) && poly_overlap(poly, q)
                            hit = true
                            break
                        end
                    end
                    hit && break
                end
                hit && (bad = "rej_overlap_run")
            end
            if !isempty(bad) && attempt == 0 && !isempty(partners)
                inc!(bv, "mitre_fail_" * bad)
            end
            if isempty(bad) || attempt == 1 || !(any(gr.wall) || !isempty(partners))
                break
            end
            gr.wall[1] = false; gr.wall[2] = false
            for e in (0, 1)
                if gr.mitre[e+1] !== nothing
                    clear_mitre!(bv, gr, e)
                    inc!(bv, "mitres_reverted_overlap")
                end
            end
            layout!(bv, gr)
            inc!(bv, "wall_ends_reverted_overlap")
        end
        if !isempty(bad)
            gr.ok = false
            inc!(bv, bad)
            continue
        end
        for (s, poly) in mine
            push!(get!(placed, s, Tuple{Vector{P2},Int}[]), (poly, gid))
        end
    end
end

# --- texture orientation (P7) ------------------------------------------------------------------------------------------
"st derivative of face f along the 3D vector e (in the face plane)."
@inline function st_deriv(f::Face, e::V3)::NTuple{2,Float64}
    a = vdot(e, f.u); b = vdot(e, f.v)
    F = f.fit
    (a * F[1, 1] + b * F[2, 1], a * F[1, 2] + b * F[2, 2])
end

der8(c) = (c.a0..., c.c0..., c.a1..., c.c1...)

struct SeamCls
    cls::Symbol      # :compat :mirror :along :scale :rot :diff
    ax::Int          # along-edge texture axis (1 = s, 2 = t), 0 = rotated
    pa::Int          # sign product wanted for the along axis (sigma_A * sigma_B)
    pc::Int          # same for the across axis
    ratio::Float64   # worst scale ratio (>= 1)
    a0::NTuple{2,Float64}; c0::NTuple{2,Float64}; a1::NTuple{2,Float64}; c1::NTuple{2,Float64}
end

"Classify the texture continuity across the edge (direction d) between faces fa and fb; wA / wB point from the edge into each face."
function seam_class(fa::Face, fb::Face, d::V3, wA::V3, wB::V3)::SeamCls
    aA = st_deriv(fa, d); cA = st_deriv(fa, -wA)
    aB = st_deriv(fb, d); cB = st_deriv(fb, wB)
    mk(c, ax=0, pa=1, pc=1, r=1.0) = SeamCls(c, ax, pa, pc, r, aA, cA, aB, cB)
    fa.shader != fb.shader && return mk(:diff)
    dom(v) = abs(v[1]) >= abs(v[2]) ? 1 : 2
    axis_ok(v, ax) = abs(v[3-ax]) <= 0.25 * abs(v[ax])
    ax = dom(aA)
    if dom(aB) != ax || !axis_ok(aA, ax) || !axis_ok(aB, ax) || !axis_ok(cA, 3 - ax) || !axis_ok(cB, 3 - ax) ||
       min(abs(aA[ax]), abs(aB[ax]), abs(cA[3-ax]), abs(cB[3-ax])) < 1e-9
        return mk(:rot)
    end
    ax2 = 3 - ax
    pa = sign(aA[ax]) == sign(aB[ax]) ? 1 : -1
    pc = sign(cA[ax2]) == sign(cB[ax2]) ? 1 : -1
    r1 = abs(aA[ax]) / abs(aB[ax]); r2 = abs(cA[ax2]) / abs(cB[ax2])
    ratio = max(r1, 1 / r1, r2, 1 / r2)
    cls = pa == -1 ? :along : pc == -1 ? :mirror : ratio > 1.15 ? :scale : :compat
    mk(cls, ax, pa, pc, ratio)
end

"Edge frame of a bevelled group for the seam test: faces and the inward directions."
function group_seam(bv::Bevel, gr::Group)
    fa, fb = face(bv, gr.fA.keys[1]), face(bv, gr.fB.keys[1])
    fa, fb, gr.d, gr.wA, gr.wB
end

"Edge frame of a concave pair."
function concave_seam(bv::Bevel, sa::Int, sb::Int, p0::V3, p1::V3)
    fa, fb = face(bv, sa), face(bv, sb)
    d = unit(p1 - p0)
    wA = unit(vcross(d, fa.n)); vdot(wA, fa.centroid - p0) < 0 && (wA = -wA)
    wB = unit(vcross(d, fb.n)); vdot(wB, fb.centroid - p0) < 0 && (wB = -wB)
    fa, fb, d, wA, wB
end

"Class table (by seam length) as a Dict, from the seam records (`which` = :cls0 or :cls)."
function class_table(bv::Bevel, which::Symbol)
    tab = Dict{Symbol,Float64}()
    for r in bv.seams
        tab[getfield(r, which)] = get(tab, getfield(r, which), 0.0) + r.len
    end
    tab
end

function flip_face!(f::Face, flips::NTuple{2,Int})
    for i in 1:length(f.A)
        a = f.A[i]
        f.A[i] = (a[1], a[2], a[3], flips[1] * a[4], flips[2] * a[5], a[6], a[7], a[8], a[9], a[10], a[11], a[12], a[13], a[14])
    end
    flips[1] < 0 && (f.fit[:, 1] .*= -1)
    flips[2] < 0 && (f.fit[:, 2] .*= -1)
end

function face_area(f::Face)
    s = 0.0
    for t in f.tris
        s += 0.5 * tri_area2(axyz(f.A[t[1]]), axyz(f.A[t[2]]), axyz(f.A[t[3]]))
    end
    s
end

"""
P7: choose an independent +-1 flip of the s and t axes for every same-shader component so that textures continue (do not mirror)
across bevelled and concave seams. Signed-graph problem per axis: maximum spanning tree for the initial labelling, then greedy
single-node improvement; unanchored connected groups keep the larger-area side unflipped. Fills `bv.seams`.
"""
function orient_components!(bv::Bevel)
    empty!(bv.seams)
    par = Dict{Int,Int}()
    function find(x)
        while get!(par, x, x) != x
            par[x] = par[par[x]]
            x = par[x]
        end
        x
    end
    for (a_, b_) in bv.coplanar_pairs
        face(bv, a_).shader == face(bv, b_).shader && (par[find(a_)] = find(b_))
    end
    # seams
    seams = Any[]   # (gid, kind weight, fa, fb, d, wA, wB, len)
    for (gid, gr) in enumerate(bv.groups)
        gr.ok || continue
        fa, fb, d, wA, wB = group_seam(bv, gr)
        push!(seams, (gid, 2.0, fa, fb, d, wA, wB, gr.hi - gr.lo, gr.P0 + d * (0.5 * (gr.lo + gr.hi))))
    end
    for (sa, sb, p0, p1) in bv.concave
        face(bv, sa).bad && continue
        face(bv, sb).bad && continue
        fa, fb, d, wA, wB = concave_seam(bv, sa, sb, p0, p1)
        len = vnorm(p1 - p0)
        len < 1.0 && continue
        push!(seams, (0, 1.0, fa, fb, d, wA, wB, len, 0.5 * (p0 + p1)))
    end
    skip_re = isempty(bv.a.flip_skip) ? nothing : Regex(bv.a.flip_skip, "i")
    nodes = Dict{Int,Int}()    # component root -> index
    for f in bv.flist
        get!(nodes, find(f.si), length(nodes) + 1)
    end
    nn = length(nodes)
    fixed = falses(nn)
    area = zeros(nn)
    for f in bv.flist
        k = nodes[find(f.si)]
        area[k] += f.bad ? 0.0 : face_area(f)
        (!bv.a.flip || (skip_re !== nothing && occursin(skip_re, last(split(f.name, '/')))) || f.bad) && (fixed[k] = true)
    end
    cls0 = SeamCls[]
    for sm in seams
        push!(cls0, seam_class(sm[3], sm[4], sm[5], sm[6], sm[7]))
    end
    # edges per axis: (na, nb, p, w)
    E = [Tuple{Int,Int,Int,Float64}[] for _ in 1:2]
    for (k, sm) in enumerate(seams)
        c = cls0[k]
        c.ax == 0 && continue
        na, nb = nodes[find(sm[3].si)], nodes[find(sm[4].si)]
        na == nb && continue
        w = sm[2] * sm[8]
        push!(E[c.ax], (na, nb, c.pa, w))
        push!(E[3-c.ax], (na, nb, c.pc, w))
    end
    sig = ones(Int, nn, 2)
    for ax in 1:2
        edges = E[ax]
        isempty(edges) && continue
        sg = solve_signed(nn, edges, fixed, area)
        sig[:, ax] = sg
    end
    nflip = 0; flen = 0.0
    byroot = Dict{Int,Vector{Int}}()
    for f in bv.flist
        push!(get!(byroot, find(f.si), Int[]), f.si)
    end
    for (root, k) in nodes
        fl = (sig[k, 1], sig[k, 2])
        fl == (1, 1) && continue
        nflip += 1
        for si in byroot[root]
            flip_face!(face(bv, si), fl)
            inc!(bv, "flip_faces")
        end
    end
    bv.stats["flip_components"] = nflip
    empty!(SEAM_CLS_OF); empty!(SEAM_OF)
    # records with classes after the flips
    for (k, sm) in enumerate(seams)
        c1 = seam_class(sm[3], sm[4], sm[5], sm[6], sm[7])
        na, nb = nodes[find(sm[3].si)], nodes[find(sm[4].si)]
        push!(bv.seams, SeamRec(sm[1], sm[8], sm[3].si, sm[4].si, sm[3].name, sm[4].name, cls0[k].cls, c1.cls,
                                (sig[na, 1], sig[na, 2]), (sig[nb, 1], sig[nb, 2]), NaN, 1.0, NaN, der8(cls0[k]), der8(c1), sm[9]))
    end
    for r in bv.seams
        r.gid > 0 && (SEAM_CLS_OF[r.gid] = r.cls; SEAM_OF[r.gid] = r)
    end
    nothing
end

"Leftover st offset (period units, fractional part) at each seam centre after alignment: bevelled seams use the unfolded points like align_textures!."
function seam_resid!(bv::Bevel)
    for r in bv.seams
        fa, fb = face(bv, r.fa), face(bv, r.fb)
        fa.shader == fb.shader || continue
        if r.gid > 0
            gr = bv.groups[r.gid]
            th = acos(max(-1.0, min(1.0, vdot(fa.n, fb.n))))
            half = th > 1e-3 ? gr.r * (th / 2) / tan(th / 2) : gr.r
            ins = V3[]
            for f_ in (fa, fb)
                w = vcross(f_.n, gr.d); w = w / vnorm(w)
                vdot(f_.centroid - gr.P0, w) < 0 && (w = -w)
                push!(ins, (gr.r - half) * w)
            end
            sa = eval_map(fa, r.pm + ins[1]); sb = eval_map(fb, r.pm + ins[2])
        else
            sa = eval_map(fa, r.pm); sb = eval_map(fb, r.pm)
        end
        d1 = sa[1] - sb[1]; d2 = sa[2] - sb[2]
        r.resid = max(abs(d1 - round(d1)), abs(d2 - round(d2)))
    end
end

"Maximise the weight of satisfied sign constraints sigma_a * sigma_b = p. Fixed nodes keep +1. Returns +-1 per node."
function solve_signed(nn::Int, edges::Vector{Tuple{Int,Int,Int,Float64}}, fixed::BitVector, area::Vector{Float64})::Vector{Int}
    adj = [Int[] for _ in 1:nn]
    for (e, (a, b, _p, _w)) in enumerate(edges)
        push!(adj[a], e); push!(adj[b], e)
    end
    # maximum spanning forest (Kruskal), fixed nodes joined to a virtual anchor so their +1 is honoured
    par = collect(1:nn + 1)
    function fnd(x)
        while par[x] != x
            par[x] = par[par[x]]; x = par[x]
        end
        x
    end
    for k in 1:nn
        fixed[k] && (par[fnd(k)] = fnd(nn + 1))
    end
    order = sortperm([-e[4] for e in edges])
    tree = Vector{Vector{Int}}(undef, nn); for k in 1:nn; tree[k] = Int[]; end
    for e in order
        a, b = edges[e][1], edges[e][2]
        ra, rb = fnd(a), fnd(b)
        ra == rb && continue
        par[ra] = rb
        push!(tree[a], e); push!(tree[b], e)
    end
    sg = zeros(Int, nn)
    # label each tree component starting from fixed nodes, then from the largest-area node
    function label!(root)
        sg[root] != 0 && return
        sg[root] = 1
        stack = [root]
        while !isempty(stack)
            a = pop!(stack)
            for e in tree[a]
                x, y, p, _w = edges[e]
                o = x == a ? y : x
                sg[o] != 0 && continue
                sg[o] = sg[a] * p
                push!(stack, o)
            end
        end
    end
    for k in 1:nn
        fixed[k] && sg[k] == 0 && label!(k)
    end
    # a tree component with several fixed nodes may conflict: the later fixed ones are reset to +1 below (counted as unsatisfied)
    for k in sortperm(-area)
        sg[k] == 0 && label!(k)
    end
    for k in 1:nn
        fixed[k] && (sg[k] = 1)
    end
    # greedy improvement
    for iter in 1:20
        changed = false
        for k in 1:nn
            fixed[k] && continue
            gain = 0.0
            for e in adj[k]
                x, y, p, w = edges[e]
                o = x == k ? y : x
                cur = sg[k] * sg[o] == p
                gain += cur ? -w : w
            end
            if gain > 1e-9
                sg[k] = -sg[k]; changed = true
            end
        end
        changed || break
    end
    # unanchored connected groups: flip the side with the smaller area
    comp = zeros(Int, nn)
    nc = 0
    for k in 1:nn
        (comp[k] != 0 || isempty(adj[k])) && continue
        nc += 1
        comp[k] = nc
        st = [k]; anch = fixed[k]; aneg = 0.0; apos = 0.0
        members = Int[]
        while !isempty(st)
            a = pop!(st)
            push!(members, a)
            fixed[a] && (anch = true)
            sg[a] < 0 ? (aneg += area[a]) : (apos += area[a])
            for e in adj[a]
                x, y = edges[e][1], edges[e][2]
                o = x == a ? y : x
                comp[o] == 0 && (comp[o] = nc; push!(st, o))
            end
        end
        if !anch && aneg > apos
            for a in members
                sg[a] = -sg[a]
            end
        end
    end
    sg
end

# --- UV alignment ------------------------------------------------------------------------------------------------------
function align_textures_greedy!(bv::Bevel)
    par = Dict{Int,Int}()
    function find(x)
        while get!(par, x, x) != x
            par[x] = par[par[x]]
            x = par[x]
        end
        x
    end
    for (a_, b_) in bv.coplanar_pairs
        if face(bv, a_).shader == face(bv, b_).shader
            par[find(a_)] = find(b_)
        end
    end
    members = Dict{Int,Vector{Int}}()
    for f in bv.flist
        push!(get!(members, find(f.si), Int[]), f.si)
    end
    fixed = Set{Int}()
    function shift!(c, off)
        for si in members[c]
            f = face(bv, si)
            for i in 1:length(f.A)
                a = f.A[i]
                f.A[i] = (a[1], a[2], a[3], a[4] + off[1], a[5] + off[2], a[6], a[7], a[8], a[9], a[10], a[11], a[12], a[13], a[14])
            end
            f.fit[3, 1] += off[1]
            f.fit[3, 2] += off[2]
        end
    end
    runs = sort([g for g in bv.groups if g.ok], by=g -> -(g.hi - g.lo), alg=MergeSort)
    for gr in runs
        fa, fb = face(bv, gr.fA.keys[1]), face(bv, gr.fB.keys[1])
        ca, cb = find(fa.si), find(fb.si)
        (ca == cb || (ca in fixed && cb in fixed)) && continue
        if fa.shader != fb.shader
            inc!(bv, "align_other_shader"); continue
        end
        ga = sqrt(abs(fa.fit[1, 1] * fa.fit[2, 2] - fa.fit[1, 2] * fa.fit[2, 1]))
        gb = sqrt(abs(fb.fit[1, 1] * fb.fit[2, 2] - fb.fit[1, 2] * fb.fit[2, 1]))
        if min(ga, gb) < 1e-9 || max(ga, gb) / min(ga, gb) > 1.5
            inc!(bv, "align_scale"); continue
        end
        th = acos(max(-1.0, min(1.0, vdot(fa.n, fb.n))))
        half = th > 1e-3 ? gr.r * (th / 2) / tan(th / 2) : gr.r
        ins = V3[]
        for f_ in (fa, fb)
            w = vcross(f_.n, gr.d)
            w = w / vnorm(w)
            vdot(f_.centroid - gr.P0, w) < 0 && (w = -w)
            push!(ins, (gr.r - half) * w)
        end
        res = NTuple{2,Float64}[]
        for tf in (0.2, 0.5, 0.8)
            pm = gr.P0 + gr.d * (gr.lo + tf * (gr.hi - gr.lo))
            sa = eval_map(fa, pm + ins[1])
            sb = eval_map(fb, pm + ins[2])
            push!(res, (sa[1] - sb[1], sa[2] - sb[2]))
        end
        if ca in fixed
            mov, sgn = cb, 1.0
        elseif cb in fixed
            mov, sgn = ca, -1.0
        else
            push!(fixed, ca)
            mov, sgn = cb, 1.0
        end
        d = res[2]
        off = (d[1] - round(d[1]), d[2] - round(d[2]))
        drift = 0.0
        for r_ in res
            for k in 1:2
                x = r_[k] - d[k]
                drift = max(drift, abs(x - round(x)))
            end
        end
        if drift > 0.15
            inc!(bv, "align_drift"); continue
        end
        shift!(mov, (sgn * off[1], sgn * off[2]))
        push!(fixed, mov)
        inc!(bv, "align_shifted")
        inc!(bv, "align_shift_sum", max(abs(off[1]), abs(off[2])))
        inc!(bv, "align_faces", length(members[mov]))
    end
end

"Global least-squares alignment: one st offset per coplanar-same-shader component, integer lifts from a spanning tree, re-rounded and re-solved."
function align_textures!(bv::Bevel)
    par = Dict{Int,Int}()
    function find(x)
        while get!(par, x, x) != x
            par[x] = par[par[x]]
            x = par[x]
        end
        x
    end
    for (a_, b_) in bv.coplanar_pairs
        if face(bv, a_).shader == face(bv, b_).shader
            par[find(a_)] = find(b_)
        end
    end
    members = Dict{Int,Vector{Int}}()
    for f in bv.flist
        push!(get!(members, find(f.si), Int[]), f.si)
    end
    function shift!(c, off)
        for si in members[c]
            f = face(bv, si)
            for i in 1:length(f.A)
                a = f.A[i]
                f.A[i] = (a[1], a[2], a[3], a[4] + off[1], a[5] + off[2], a[6], a[7], a[8], a[9], a[10], a[11], a[12], a[13], a[14])
            end
            f.fit[3, 1] += off[1]
            f.fit[3, 2] += off[2]
        end
    end
    # edges: (ca, cb, r = st(A) - st(B) at the seam, weight = run length)
    EA = Int[]; EB = Int[]; ER = NTuple{2,Float64}[]; EW = Float64[]
    for gr in bv.groups
        gr.ok || continue
        fa, fb = face(bv, gr.fA.keys[1]), face(bv, gr.fB.keys[1])
        ca, cb = find(fa.si), find(fb.si)
        ca == cb && (inc!(bv, "align_same_component"); continue)
        if fa.shader != fb.shader
            inc!(bv, "align_other_shader"); continue
        end
        ga = sqrt(abs(fa.fit[1, 1] * fa.fit[2, 2] - fa.fit[1, 2] * fa.fit[2, 1]))
        gb = sqrt(abs(fb.fit[1, 1] * fb.fit[2, 2] - fb.fit[1, 2] * fb.fit[2, 1]))
        if min(ga, gb) < 1e-9 || max(ga, gb) / min(ga, gb) > 1.5
            inc!(bv, "align_scale"); continue
        end
        th = acos(max(-1.0, min(1.0, vdot(fa.n, fb.n))))
        half = th > 1e-3 ? gr.r * (th / 2) / tan(th / 2) : gr.r
        ins = V3[]
        for f_ in (fa, fb)
            w = vcross(f_.n, gr.d)
            w = w / vnorm(w)
            vdot(f_.centroid - gr.P0, w) < 0 && (w = -w)
            push!(ins, (gr.r - half) * w)
        end
        res = NTuple{2,Float64}[]
        for tf in (0.2, 0.5, 0.8)
            pm = gr.P0 + gr.d * (gr.lo + tf * (gr.hi - gr.lo))
            sa = eval_map(fa, pm + ins[1])
            sb = eval_map(fb, pm + ins[2])
            push!(res, (sa[1] - sb[1], sa[2] - sb[2]))
        end
        d = res[2]
        drift = 0.0
        for r_ in res, k in 1:2
            x = r_[k] - d[k]
            drift = max(drift, abs(x - round(x)))
        end
        if drift > 0.15
            inc!(bv, "align_drift"); continue
        end
        push!(EA, ca); push!(EB, cb); push!(ER, d); push!(EW, gr.hi - gr.lo)
    end
    ne = length(EA)
    adj = Dict{Int,Vector{Int}}()
    for e in 1:ne
        push!(get!(adj, EA[e], Int[]), e)
        push!(get!(adj, EB[e], Int[]), e)
    end
    off = Dict{Int,NTuple{2,Float64}}()
    comp = Dict{Int,Int}()    # node -> root of its edge-graph component
    nodes_of = Dict{Int,Vector{Int}}()
    for root in sort(collect(keys(adj)))
        haskey(off, root) && continue
        off[root] = (0.0, 0.0); comp[root] = root
        nodes_of[root] = [root]
        queue = [root]
        qi = 1
        while qi <= length(queue)
            a = queue[qi]; qi += 1
            for e in adj[a]
                other = EA[e] == a ? EB[e] : EA[e]
                haskey(off, other) && continue
                oa = off[a]; r = ER[e]
                # want st_A + o_A == st_B + o_B  ->  o_B = o_A + r
                off[other] = EA[e] == a ? (oa[1] + r[1], oa[2] + r[2]) : (oa[1] - r[1], oa[2] - r[2])
                comp[other] = root
                push!(nodes_of[root], other)
                push!(queue, other)
            end
        end
    end
    # integer lifts re-rounded; LS solve with Gauss-Seidel
    kk = [(0.0, 0.0) for _ in 1:ne]
    EW0 = copy(EW)
    for iter in 1:10
        for e in 1:ne
            oa, ob, r = off[EA[e]], off[EB[e]], ER[e]
            kk[e] = (round(r[1] + oa[1] - ob[1]), round(r[2] + oa[2] - ob[2]))
        end
        for sweep in 1:200
            for (n, es) in adj
                sx = sy = sw = 0.0
                for e in es
                    w = EW[e]; r = ER[e]; k = kk[e]
                    # a = EA: o_A - o_B = k - r
                    if EA[e] == n
                        ob = off[EB[e]]
                        sx += w * (ob[1] + k[1] - r[1]); sy += w * (ob[2] + k[2] - r[2])
                    else
                        oa = off[EA[e]]
                        sx += w * (oa[1] - k[1] + r[1]); sy += w * (oa[2] - k[2] + r[2])
                    end
                    sw += w
                end
                off[n] = (sx / sw, sy / sw)
            end
        end
        # IRLS: edges that stay inconsistent (cycle conflicts) lose weight so they stop dragging the consistent ones
        for e in 1:ne
            oa, ob, r = off[EA[e]], off[EB[e]], ER[e]
            x1 = r[1] + oa[1] - ob[1]; x2 = r[2] + oa[2] - ob[2]
            rs = max(abs(x1 - round(x1)), abs(x2 - round(x2)))
            EW[e] = EW0[e] / max(1.0, rs / 0.02)^2
        end
    end
    EW .= EW0
    tot = 0.0; good = 0.0
    for e in 1:ne
        oa, ob, r = off[EA[e]], off[EB[e]], ER[e]
        x1 = r[1] + oa[1] - ob[1]; x2 = r[2] + oa[2] - ob[2]
        resid = max(abs(x1 - round(x1)), abs(x2 - round(x2)))
        tot += EW[e]
        if resid < 0.05
            good += EW[e]
        else
            inc!(bv, "align_cycle_skips")
        end
        inc!(bv, "align_edges")
    end
    bv.stats["align_len_total"] = tot
    bv.stats["align_len_good"] = good
    for (root, ns) in nodes_of
        o0 = off[root]
        for n in ns
            o = off[n]
            shift!(n, (o[1] - floor(o[1] + 0.5), o[2] - floor(o[2] + 0.5)))
            inc!(bv, "align_shifted")
            inc!(bv, "align_faces", length(members[n]))
            inc!(bv, "align_shift_sum", max(abs(o[1] - floor(o[1] + 0.5)), abs(o[2] - floor(o[2] + 0.5))))
        end
    end
end
