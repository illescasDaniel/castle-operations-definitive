# World bevel, part 3: face clipping, strip / corner / wall-cap generation, assembly of the new lumps, driver.

function profile_bps(gr::Group, side::Int)
    bps, cv = copy(gr.bps), copy(gr.cvals)
    m0, m1 = gr.mitre[1], gr.mitre[2]
    if m0 !== nothing && m0.P == gr.pk[side+1]
        pushfirst!(bps, gr.lo - gr.r); pushfirst!(cv, gr.r)
    end
    if m1 !== nothing && m1.P == gr.pk[side+1]
        push!(bps, gr.hi + gr.r); push!(cv, gr.r)
    end
    bps, cv
end

@inline dists(P::Poly, P0::V3, w::V3) = Float64[vdot(axyz(q) - P0, w) for q in P]

function insert_online(up::Poly, online::Vector{Att}, P0::V3, w::V3, d::V3, r::Float64)::Poly
    isempty(online) && return up
    s = dists(up, P0, w)
    on = [i for i in 1:length(up) if abs(s[i] - r) < 1e-7]
    length(on) != 2 && return up
    k = length(up)
    i0, i1 = on[1], on[2]
    if i0 % k + 1 == i1
        a_i, b_i = i0, i1
    elseif i1 % k + 1 == i0
        a_i, b_i = i1, i0
    else
        return up
    end
    ta = vdot(axyz(up[a_i]) - P0, d)
    tb = vdot(axyz(up[b_i]) - P0, d)
    lo, hi = min(ta, tb), max(ta, tb)
    ins = Tuple{Float64,Att}[]
    seen = Float64[]
    for q in online
        tq = vdot(axyz(q) - P0, d)
        if lo + 1e-6 < tq < hi - 1e-6 && !any(x -> abs(tq - x) < 1e-6, seen)
            push!(seen, tq)
            push!(ins, (tq, q))
        end
    end
    isempty(ins) && return up
    sort!(ins, by=x -> x[1], rev=ta > tb, alg=MergeSort)
    rows = copy(up)
    splice!(rows, b_i:b_i-1, Att[q for (_t, q) in ins])
    rows
end

function cut_face!(bv::Bevel, f::Face, gr::Group, w::V3, side::Int)
    ensure_polys!(f)
    bps, cvals = profile_bps(gr, side)
    r = gr.r
    P0, d = gr.P0, gr.d
    out = Poly[]
    for P0poly in f.polys
        P = P0poly
        s = dists(P, P0, w)
        if maximum(s) <= 1e-9
            push!(out, P); continue
        end
        if minimum(s) < -1e-9
            Pp, Pb = split_plane(P, s)
            Pb !== nothing && push!(out, Pb)
            Pp === nothing && continue
            P = Pp
            s = dists(P, P0, w)
        end
        t = dists(P, P0, d)
        if minimum(s) >= r - 1e-9 || maximum(t) <= bps[1] + 1e-9 || minimum(t) >= bps[end] - 1e-9
            push!(out, P); continue
        end
        up, low = split_plane(P, s .- r)
        pieces = low !== nothing ? Poly[low] : Poly[]
        for b in bps
            nxt = Poly[]
            for pc in pieces
                tp = dists(pc, P0, d)
                p1, p2 = split_plane(pc, tp .- b)
                p1 !== nothing && push!(nxt, p1)
                p2 !== nothing && push!(nxt, p2)
            end
            pieces = nxt
        end
        kept = Poly[]
        online = Att[]
        for pc in pieces
            tp = dists(pc, P0, d)
            tm = sum(tp) / length(tp)
            if tm <= bps[1] || tm >= bps[end]
                push!(kept, pc)
            else
                k = 0
                for kk in 1:length(bps)-1
                    if bps[kk] <= tm <= bps[kk+1]
                        k = kk; break
                    end
                end
                if k == 0
                    push!(kept, pc); continue
                end
                ta, tb = bps[k], bps[k+1]
                c0, c1 = cvals[k], cvals[k+1]
                sp = dists(pc, P0, w)
                sd = Float64[sp[i] - (c0 + (c1 - c0) * (tp[i] - ta) / (tb - ta)) for i in 1:length(pc)]
                pos, _neg = split_plane(pc, sd)
                pos === nothing && continue
                push!(kept, pos)
            end
            for q in pc
                abs(vdot(axyz(q) - P0, w) - r) < 1e-7 && push!(online, q)
            end
        end
        if up !== nothing
            push!(out, insert_online(up, online, P0, w, d, r))
        end
        append!(out, kept)
    end
    f.polys = out
end

# --- strip -------------------------------------------------------------------------------------------------------------
function actual_end(tk::Vector{Float64}, pk::Vector{V3}, t::Float64, fallback::V3)::V3
    length(tk) < 2 && return fallback
    i = searchsortedfirst(tk, t)
    (i <= length(tk) && abs(tk[i] - t) < 5e-4) && return pk[i]
    (i > 1 && abs(tk[i-1] - t) < 5e-4) && return pk[i-1]
    (i == 1 || i > length(tk)) && return fallback
    u = (t - tk[i-1]) / (tk[i] - tk[i-1])
    pk[i-1] + u * (pk[i] - pk[i-1])
end

function thin_rows(bv::Bevel, gr::Group, ts::Vector{Float64}, polys)
    forced = [1, length(ts)]
    for b in vcat([gr.te_lo, gr.te_hi], [b for b in gr.bps if gr.te_lo - 1e-6 <= b <= gr.te_hi + 1e-6])
        push!(forced, argmin([abs(t - b) for t in ts]))
    end
    keep = sort!(unique(forced))
    todo = [(keep[k], keep[k+1]) for k in 1:length(keep)-1]
    while !isempty(todo)
        i0, i1 = pop!(todo)
        i1 - i0 < 2 && continue
        ta, tb = ts[i0], ts[i1]
        best, bd = 0, bv.a.row_tol
        for (tk, pk) in polys
            length(tk) < 2 && continue
            pa, pb = actual_end(tk, pk, ta, ZERO3), actual_end(tk, pk, tb, ZERO3)
            # python skips when the end is None (no fallback); approximate: skip when poly has < 2 rows
            for i in i0+1:i1-1
                t = ts[i]
                pt = actual_end(tk, pk, t, ZERO3)
                u = (t - ta) / (tb - ta)
                dev = vnorm(pt - (pa + u * (pb - pa)))
                if dev > bd
                    best, bd = i, dev
                end
            end
        end
        if best != 0
            push!(keep, best)
            push!(todo, (i0, best)); push!(todo, (best, i1))
        end
    end
    inc!(bv, "strip_rows_candidate", length(ts))
    inc!(bv, "strip_rows_kept", length(unique(keep)))
    [ts[i] for i in sort!(unique(keep))]
end

"P9: for a seam between faces with different shaders, the face whose shader (and unfolded mapping) covers the whole curve; nothing otherwise."
function wrap_owner(bv::Bevel, gr::Group, fa::Face, fb::Face)::Union{Nothing,Face}
    pref = bv.a.wrap_prefer
    (pref == "off" || fa.shader == fb.shader) && return nothing
    (fa.has_lm && fb.has_lm) || return nothing
    function width(f::Face, w::V3)
        maximum(vdot(axyz(q) - gr.P0, w) for q in f.A)
    end
    wa, wb = width(fa, gr.wA), width(fb, gr.wB)
    pref == "wide" ? (wa >= wb ? fa : fb) : (wa <= wb ? fa : fb)
end

function build_strip!(bv::Bevel, gr::Group, gid::Int)
    a = bv.a
    rows = Set{Float64}(round(b, digits=6) for b in gr.bps if gr.te_lo - 1e-6 <= b <= gr.te_hi + 1e-6)
    push!(rows, round(gr.te_lo, digits=6)); push!(rows, round(gr.te_hi, digits=6))
    for store in (gr.fA, gr.fB)
        for s in store.keys
            for cv in face(bv, s).cutverts
                if cv.gid == gid && gr.te_lo - 1e-6 <= cv.t <= gr.te_hi + 1e-6
                    push!(rows, round(cv.t, digits=6))
                end
            end
        end
    end
    ts0 = sort!(collect(rows))
    ts = Float64[ts0[1]]
    for t in ts0[2:end]
        t - ts[end] > 5e-4 && push!(ts, t)
    end
    N = max(1, a.segments)
    phis = sort!(unique(vcat([k / N for k in 0:N], [0.5])))
    np = length(phis)
    im = findfirst(==(0.5), phis)
    theta = gr.theta

    function polyline(store::Store)
        pts = Dict{Float64,V3}()
        for sid in store.keys
            for cv in face(bv, sid).cutverts
                cv.gid == gid && !haskey(pts, round(cv.t, digits=4)) && (pts[round(cv.t, digits=4)] = cv.pos)
            end
        end
        k = sort!(collect(keys(pts)))
        k, V3[pts[x] for x in k]
    end
    polyA, polyB = polyline(gr.fA), polyline(gr.fB)

    if a.row_tol > 0 && length(ts) > 2
        ts = thin_rows(bv, gr, ts, (polyA, polyB))
    end

    end_row = Dict{Float64,Int}()
    for e in (0, 1)
        gr.wall[e+1] || continue
        ex = Float64[(e == 0 ? pl[1][1] : pl[1][end]) for pl in (polyA, polyB) if !isempty(pl[1])]
        tref = !isempty(ex) ? (e == 0 ? maximum(ex) : minimum(ex)) : (e == 0 ? ts[1] : ts[end])
        ts = e == 0 ? vcat([tref], [t for t in ts if t > tref + 5e-4]) : vcat([t for t in ts if t < tref - 5e-4], [tref])
        end_row[round(tref, digits=6)] = e
    end

    rowsd = Row[]
    for t in ts
        c = c_at(gr, t)
        R = c * gr.R_over_c
        E = gr.P0 + gr.d * t
        K = E + c * gr.wA - R * gr.nA
        Kb = E + c * gr.wB - R * gr.nB
        vmaxabs(K - Kb) > 1e-6 && inc!(bv, "strip_center_mismatch")
        nrm = V3[slerp(gr.nA, gr.nB, p, theta) for p in phis]
        tA, tB = K + R * nrm[1], K + R * nrm[end]
        dA = actual_end(polyA[1], polyA[2], t, tA) - tA
        dB = actual_end(polyB[1], polyB[2], t, tB) - tB
        pts = V3[K + R * nrm[k] + (1 - phis[k]) * dA + phis[k] * dB for k in 1:np]
        rt = round(t, digits=6)
        if haskey(end_row, rt)
            e = end_row[rt]
            nW, dW = gr.wall_pl[e+1]
            for k in 1:np
                pts[k] = pts[k] + ((dW - vdot(nW, pts[k])) / vdot(nW, gr.d)) * gr.d
            end
            for (k, pl) in ((1, polyA), (np, polyB))
                if !isempty(pl[1])
                    q_ = e == 0 ? pl[2][1] : pl[2][end]
                    vnorm(q_ - pts[k]) > 0.3 && inc!(bv, "wall_end_row_mismatch")
                    pts[k] = q_
                end
            end
        end
        push!(rowsd, Row(t, c, pts, nrm))
    end
    for e in (0, 1)
        mt = gr.mitre[e+1]
        mt === nothing && continue
        base = e == 0 ? rowsd[1] : rowsd[end]
        u = e == 0 ? gr.d : -gr.d
        p_first = gr.pk[1] == mt.P
        kidx(k) = p_first ? k : np + 1 - k
        slid = Vector{V3}(undef, np)
        for k in 1:np
            X = base.pts[k]
            slid[kidx(k)] = X - (vdot(mt.nPi, X - mt.V) / vdot(mt.nPi, u)) * u
        end
        sh = mt.shared
        if sh.pts === nothing
            best, bd = nothing, 0.3
            for sid in (p_first ? gr.fA : gr.fB).keys
                for P in face(bv, sid).polys
                    for q in P
                        dd = vnorm(axyz(q) - slid[1])
                        if dd < bd
                            best, bd = axyz(q), dd
                        end
                    end
                end
            end
            if best === nothing
                inc!(bv, "mitre_corner_vertex_missing")
            else
                slid[1] = best
            end
            sh.pts = slid
        elseif maximum(vnorm(sh.pts[k] - slid[k]) for k in 1:np) > 0.1
            inc!(bv, "mitre_asymmetric")
        end
        tl = e == 0 ? base.t - gr.r : base.t + gr.r
        row = Row(tl, base.c, V3[sh.pts[kidx(k)] for k in 1:np], base.nms)
        e == 0 ? pushfirst!(rowsd, row) : push!(rowsd, row)
    end
    gr.row_first, gr.row_last = rowsd[1], rowsd[end]

    function pick(store::Store, tm::Float64)
        best, bd = 0, 1e18
        for (s, (t0, t1)) in zip(store.keys, store.ext)
            dd = (t0 - 1e-3 <= tm <= t1 + 1e-3) ? 0.0 : min(abs(tm - t0), abs(tm - t1))
            if dd < bd
                best, bd = s, dd
            end
        end
        face(bv, best)
    end

    cache = Dict{NTuple{6,Int64},Att}()
    pairs = Dict{Tuple{Int,Int},Union{Nothing,NTuple{2,Float64}}}()

    function pair_k(fa::Face, fb::Face, tm::Float64)
        key = (fa.si, fb.si)
        haskey(pairs, key) && return pairs[key]
        k = nothing
        if a.uv_mode != "morph"
        elseif fa.shader != fb.shader
            inc!(bv, "uv_seam_pairs_other_shader")
        else
            ga = sqrt(abs(fa.fit[1, 1] * fa.fit[2, 2] - fa.fit[1, 2] * fa.fit[2, 1]))
            gb = sqrt(abs(fb.fit[1, 1] * fb.fit[2, 2] - fb.fit[1, 2] * fb.fit[2, 1]))
            if min(ga, gb) < 1e-9 || max(ga, gb) / min(ga, gb) > 1.5
                inc!(bv, "uv_seam_pairs_scale_fallback")
            else
                pm = gr.P0 + gr.d * tm
                ma, mb = eval_map(fa, pm), eval_map(fb, pm)
                dst = (ma[1] - mb[1], ma[2] - mb[2])
                k = (round(dst[1]), round(dst[2]))
                inc!(bv, "uv_residual_sum", max(abs(dst[1] - k[1]), abs(dst[2] - k[2])))
                inc!(bv, "uv_morph_pairs")
            end
        end
        pairs[key] = k
        k
    end

    function unfold(f::Face, rowpts::Vector{V3}, kt::Int)
        sideA = f.si in gr.fA
        seq = sideA ? (1:np) : (np:-1:1)
        arc = 0.0
        if seq[1] != kt
            for m in 1:length(seq)-1
                arc += vnorm(rowpts[seq[m+1]] - rowpts[seq[m]])
                seq[m+1] == kt && break
            end
        end
        c = rowpts[seq[1]]
        ed = gr.P0 + gr.d * vdot(c - gr.P0, gr.d)
        w = ed - c
        w = w - vdot(w, f.n) * f.n
        nw = vnorm(w)
        nw > 1e-9 ? c + (w / nw) * arc : c
    end

    function vert(f::Face, x::V3, nrm::V3, ph::Int, fo::Face, k, rowpts::Vector{V3})::Att
        key = (Int64(f.si), Int64(fo.si), round(Int64, x.x * 1e5), round(Int64, x.y * 1e5), round(Int64, x.z * 1e5), Int64(ph))
        v = get(cache, key, nothing)
        if v === nothing
            if a.uv_mode == "align" || a.uv_mode == "align-greedy"
                m = eval_map(f, unfold(f, rowpts, ph))
            else
                m = eval_map(f, x - vdot(x - gr.P0, f.n) * f.n)
            end
            if k === nothing && f.shader == fo.shader && a.align_stretch > 0 && a.uv_mode == "align"
                # leftover texture offset between the faces: spread it over the strip so both halves meet at the centre column
                fa_, fb_ = f.si in gr.fA ? (f, fo) : (fo, f)
                ma, mb = eval_map(fa_, unfold(fa_, rowpts, im)), eval_map(fb_, unfold(fb_, rowpts, im))
                d1, d2 = mb[1] - ma[1], mb[2] - ma[2]
                d1 -= round(d1); d2 -= round(d2)
                if max(abs(d1), abs(d2)) <= a.align_stretch && max(abs(d1), abs(d2)) > 1e-4
                    e = f === fa_ ? phis[ph] / 0.5 : (1 - phis[ph]) / 0.5
                    sg = f === fa_ ? 0.5 : -0.5
                    m = (m[1] + sg * d1 * e, m[2] + sg * d2 * e, m[3], m[4])
                    inc!(bv, "strip_offset_ramped")
                end
            end
            if k !== nothing
                fa_, fb_ = f.si in gr.fA ? (f, fo) : (fo, f)
                sa, sb = eval_map(fa_, x), eval_map(fb_, x)
                e = phis[ph] * phis[ph] * (3 - 2 * phis[ph])
                m = ((1 - e) * sa[1] + e * (sb[1] + k[1]), (1 - e) * sa[2] + e * (sb[2] + k[2]), m[3], m[4])
            end
            v = mkatt(x, m, nrm, nearest_color(f, x))
            cache[key] = v
        end
        v
    end

    added = 0
    cur = Any[nothing, nothing]    # per half: (LmBlock, id, partner surface) being extended
    nint = length(rowsd) - 1
    cls = get(SEAM_CLS_OF, gid, :none)
    ROWS_OF[gid] = Float64[r.t for r in rowsd]
    lmdev = 0.0
    zero6 = (0f0, 0f0, 0f0, 0f0, 0f0, 0f0)
    for ri in 1:nint
        ra, rb = rowsd[ri], rowsd[ri+1]
        if ra.c == 0.0 && rb.c == 0.0
            cur[1] = nothing; cur[2] = nothing
            continue
        end
        tm = 0.5 * (ra.t + rb.t)
        fa_, fb_ = pick(gr.fA, tm), pick(gr.fB, tm)
        diag_step!(bv, fa_, fb_, ra.pts[1], ra.pts[np])
        if a.lm_blend
            lmdev = max(lmdev, diag_rows!(bv, fa_, fb_, ra, rb, np))
        end
        if a.lm_blend && (ri == 1 || ri == nint) && fa_.has_lm && fb_.has_lm
            for (isend, e, rw) in ((ri == 1, 0, ra), (ri == nint, 1, rb))
                isend || continue
                LA, LB = ab_light(bv, fa_, fb_, rw.pts[1], rw.pts[np])
                bv.endcol[(gid, e)] = cols_from(LA, LB, phis, 1:np)
            end
        end
        own = wrap_owner(bv, gr, fa_, fb_)
        own !== nothing && inc!(bv, "wrap_intervals")
        for half in (0, 1)
            f = half == 0 ? fa_ : fb_
            fo = half == 0 ? fb_ : fa_
            kk = half == 0 ? pair_k(f, fo, tm) : pair_k(fo, f, tm)
            if own !== nothing
                f = own; fo = own === fa_ ? fb_ : fa_; kk = nothing
            end
            phs = half == 0 ? (1:im) : (im:np)
            blk = nothing; bid = 0; rr0 = 0f0; rr1 = 0f0
            if a.lm_blend && f.has_lm
                blk, bid, r0_, r1_ = strip_block!(bv, cur, half + 1, fa_, fb_, half, ra, rb, phis, im, np, cls, f)
                rr0 = Float32(r0_); rr1 = Float32(r1_)
            else
                cur[half+1] = nothing
            end
            for k in first(phs):last(phs)-1
                q00 = vert(f, ra.pts[k], ra.nms[k], k, fo, kk, ra.pts)
                q01 = vert(f, ra.pts[k+1], ra.nms[k+1], k + 1, fo, kk, ra.pts)
                q10 = vert(f, rb.pts[k], rb.nms[k], k, fo, kk, rb.pts)
                q11 = vert(f, rb.pts[k+1], rb.nms[k+1], k + 1, fo, kk, rb.pts)
                if blk !== nothing
                    c0 = Float32(k - first(phs) + 1); c1 = c0 + 1f0
                    ps = ((rr0, c0, rr1, c0, rr1, c1), (rr0, c0, rr1, c1, rr0, c1))
                else
                    ps = (zero6, zero6)
                end
                for (ti, T) in enumerate(((q00, q10, q11), (q00, q11, q01)))
                    p6 = ps[ti]
                    cr = vcross(axyz(T[2]) - axyz(T[1]), axyz(T[3]) - axyz(T[1]))
                    if vnorm(cr) < 1e-6
                        inc!(bv, "strip_tris_degenerate_skipped"); continue
                    end
                    navg = anrm(T[1]) + anrm(T[2]) + anrm(T[3])
                    if f.winding * vdot(cr, navg) < 0
                        T = (T[1], T[3], T[2])
                        p6 = (p6[1], p6[2], p6[5], p6[6], p6[3], p6[4])
                    end
                    push_strip!(f, T, 0x01, gid, bid, p6)
                    added += 1
                end
            end
        end
    end
    haskey(SEAM_OF, gid) && (SEAM_OF[gid].lmdev = lmdev)
    added
end

function build_wall_cap!(bv::Bevel, gr::Group, e::Int, gid::Int=0)
    row = e == 0 ? gr.row_first : gr.row_last
    pts = row.pts
    nW, dW = gr.wall_pl[e+1]
    E = gr.P0 + gr.d * ((dW - vdot(nW, gr.P0)) / vdot(nW, gr.d))
    best, bd = nothing, 1e18
    for sid in gr.fA.keys
        f = face(bv, sid)
        dd = minimum(vnorm(axyz(q) - E) for q in f.A)
        if dd < bd
            best, bd = f, dd
        end
    end
    f = best
    cache = Dict{NTuple{3,Int64},Att}()
    function vert(x::V3)
        key = (round(Int64, x.x * 1e5), round(Int64, x.y * 1e5), round(Int64, x.z * 1e5))
        get!(cache, key) do
            m = eval_map(f, x - (vdot(x, f.n) - f.d) * f.n)
            mkatt(x, m, nW, nearest_color(f, x))
        end
    end
    vE = vert(E)
    ec = get(bv.endcol, (gid, e), nothing)
    ecm = ec === nothing ? nothing : col_mean(ec)
    bv.a.lm_blend && f.has_lm || (ec = nothing)
    for k in 1:length(pts)-1
        T = (vE, vert(pts[k]), vert(pts[k+1]))
        cr = vcross(axyz(T[2]) - axyz(T[1]), axyz(T[3]) - axyz(T[1]))
        vnorm(cr) < 1e-6 && continue
        if f.winding * vdot(cr, anrm(T[1]) + anrm(T[2]) + anrm(T[3])) < 0
            T = (T[1], T[3], T[2])
        end
        bid = 0; p6 = (0f0, 0f0, 0f0, 0f0, 0f0, 0f0)
        if ec !== nothing && ec isa Vector
            # T may have been reordered: colour by vertex identity
            colof(a_) = a_ === vE ? ecm : (a_ === vert(pts[k]) ? ec[k] : ec[k+1])
            bid, p6 = tri_block!(bv, f, (colof(T[1]), colof(T[2]), colof(T[3])))
        end
        push_strip!(f, T, 0x03, gid, bid, p6)
        inc!(bv, "wall_cap_tris")
    end
    isempty(pts) || (push!(bv.cap_edges, (E, pts[1])); push!(bv.cap_edges, (E, pts[end])))
    inc!(bv, "wall_caps")
end

"Is point x (on the plane of normal n) inside one of the convex polygons (tolerance tol units)?"
function in_polys(polys::Vector{Poly}, n::V3, x::V3, tol::Float64)
    for P in polys
        m = length(P)
        m < 3 && continue
        inside = true
        for i in 1:m
            a = axyz(P[i]); b = axyz(P[i == m ? 1 : i + 1])
            e = b - a
            el = vnorm(e)
            el < 1e-9 && continue
            # signed distance to the edge line, positive inside for CCW polys about n (sign fixed by the poly's own winding)
            c = vdot(vcross(e, x - a), n) / el
            P_sign = vdot(vcross(axyz(P[2]) - axyz(P[1]), axyz(P[3]) - axyz(P[2])), n) >= 0 ? 1.0 : -1.0
            if P_sign * c < -tol
                inside = false; break
            end
        end
        inside && return true
    end
    false
end

"After all cuts: does the (unbuilt) cap fan of end e of gr leave part of the wall plane uncovered by the wall faces' final polygons?"
function cap_uncovered(bv::Bevel, gr::Group, e::Int)
    row = e == 0 ? gr.row_first : gr.row_last
    row === nothing && return false
    pts = row.pts
    nW, dW = gr.wall_pl[e+1]
    E = gr.P0 + gr.d * ((dW - vdot(nW, gr.P0)) / vdot(nW, gr.d))
    wf = Face[face(bv, si) for si in gr.wall_fi[e+1]]
    for f in wf
        ensure_polys!(f)
    end
    for k in 1:length(pts)-1
        a, b, c = E, pts[k], pts[k+1]
        vnorm(vcross(b - a, c - a)) < 1e-6 && continue
        for (wa, wb, wc) in ((1/3, 1/3, 1/3), (0.6, 0.2, 0.2), (0.2, 0.6, 0.2), (0.2, 0.2, 0.6), (0.05, 0.475, 0.475), (0.1, 0.8, 0.1), (0.1, 0.1, 0.8))
            x = wa * a + wb * b + wc * c
            any(f -> in_polys(f.polys, f.n, x, 0.05), wf) || return true
        end
    end
    false
end

function build_corner!(bv::Bevel, cr::Corner)
    arcs = []
    for (gid, e) in cr.ends
        gr = bv.groups[gid]
        row = e == 0 ? gr.row_first : gr.row_last
        ecl = get(bv.endcol, (gid, e), nothing)
        push!(arcs, (gr.pk[1], gr.pk[2], [(row.pts[k], row.nms[k], ecl === nothing ? nothing : ecl[k]) for k in 1:length(row.pts)], gr))
    end
    first_ = popfirst!(arcs)
    loop = copy(first_[3])
    cur = first_[2]
    while !isempty(arcs)
        k = findfirst(ar -> cur == ar[1] || cur == ar[2], arcs)
        ar = splice!(arcs, k)
        seq = ar[1] == cur ? ar[3] : reverse(ar[3])
        append!(loop, seq[2:end])
        cur = ar[1] == cur ? ar[2] : ar[1]
    end
    pop!(loop)
    X = V3[l[1] for l in loop]
    Nn = V3[l[2] for l in loop]
    LC = bv.a.lm_blend && all(l -> l[3] !== nothing, loop) ? NTuple{3,Float64}[l[3] for l in loop] : nothing
    LCm = LC === nothing ? nothing : col_mean(LC)
    R = sum(bv.groups[g].r * bv.groups[g].R_over_c for (g, _e) in cr.ends) / 3
    s = ZERO3
    for i in 1:length(X)
        s = s + (X[i] - R * Nn[i])
    end
    K0 = s / length(X)
    us = ZERO3
    for (g, _e) in cr.ends
        us = us + (bv.groups[g].nA + bv.groups[g].nB)
    end
    u0 = unit(us)
    m = length(loop)
    rn = V3[unit(0.5 * Nn[i] + 0.5 * u0) for i in 1:m]
    ring = V3[K0 + R * rn[i] for i in 1:m]
    ctr = K0 + R * u0
    pf = Tuple{Int,Float64,Face}[]  # (plane id, dist, face) in insertion order
    for (gid, _e) in cr.ends
        gr = bv.groups[gid]
        for (pid, store) in ((gr.pk[1], gr.fA), (gr.pk[2], gr.fB))
            for sid in store.keys
                f = face(bv, sid)
                dd = minimum(vnorm(axyz(q) - cr.pos) for q in f.A)
                i = findfirst(x -> x[1] == pid, pf)
                if i === nothing
                    push!(pf, (pid, dd, f))
                elseif dd < pf[i][2]
                    pf[i] = (pid, dd, f)
                end
            end
        end
    end
    function pn(pid)
        for (gid, _e) in cr.ends
            gr = bv.groups[gid]
            gr.pk[1] == pid && return gr.nA
            gr.pk[2] == pid && return gr.nB
        end
    end
    function pd(pid)
        for (gid, _e) in cr.ends
            gr = bv.groups[gid]
            gr.pk[1] == pid && return face(bv, gr.fA.keys[1]).d
            gr.pk[2] == pid && return face(bv, gr.fB.keys[1]).d
        end
    end
    cache = Dict{Tuple{Int,Int64,Int64,Int64},Att}()
    function vert(f::Face, x::V3, n::V3)
        key = (f.si, round(Int64, x.x * 1e5), round(Int64, x.y * 1e5), round(Int64, x.z * 1e5))
        get!(cache, key) do
            mm = eval_map(f, x - (vdot(x, f.n) - f.d) * f.n)
            mkatt(x, mm, n, nearest_color(f, x))
        end
    end
    tris = Tuple{Tuple{V3,V3,Any},Tuple{V3,V3,Any},Tuple{V3,V3,Any}}[]
    xc(i) = LC === nothing ? nothing : LC[i]
    rc(i) = LC === nothing ? nothing : col_lerp(LC[i], LCm, 0.5)
    for i in 1:m
        j = i % m + 1
        push!(tris, ((X[i], Nn[i], xc(i)), (X[j], Nn[j], xc(j)), (ring[j], rn[j], rc(j))))
        push!(tris, ((X[i], Nn[i], xc(i)), (ring[j], rn[j], rc(j)), (ring[i], rn[i], rc(i))))
        push!(tris, ((ring[i], rn[i], rc(i)), (ring[j], rn[j], rc(j)), (ctr, u0, LCm)))
    end
    for tri in tris
        g = (tri[1][1] + tri[2][1] + tri[3][1]) / 3
        bestp, bv_ = 0, Inf
        for (pid, _dd, _f) in pf
            v = abs(vdot(pn(pid), g) - pd(pid))
            if v < bv_
                bv_ = v; bestp = pid
            end
        end
        f = pf[findfirst(x -> x[1] == bestp, pf)][3]
        T = (vert(f, tri[1][1], tri[1][2]), vert(f, tri[2][1], tri[2][2]), vert(f, tri[3][1], tri[3][2]))
        cl = (tri[1][3], tri[2][3], tri[3][3])
        c = vcross(axyz(T[2]) - axyz(T[1]), axyz(T[3]) - axyz(T[1]))
        vnorm(c) < 1e-6 && continue
        if f.winding * vdot(c, anrm(T[1]) + anrm(T[2]) + anrm(T[3])) < 0
            T = (T[1], T[3], T[2])
            cl = (cl[1], cl[3], cl[2])
        end
        bid = 0; p6 = (0f0, 0f0, 0f0, 0f0, 0f0, 0f0)
        if f.has_lm && cl[1] !== nothing
            bid, p6 = tri_block!(bv, f, cl)
        end
        push_strip!(f, T, 0x02, 0, bid, p6)
        inc!(bv, "corner_patch_tris")
    end
    inc!(bv, "corner_patches")
end

# --- assembly ----------------------------------------------------------------------------------------------------------
const Q14 = NTuple{14,Float32}

function quant(T::Tri)::NTuple{3,Q14}
    q(a::Att) = ntuple(i -> i <= 10 ? Float32(a[i]) : Float32(clamp(round(a[i]), 0.0, 255.0)), Val(14))
    (q(T[1]), q(T[2]), q(T[3]))
end

function good(Q::NTuple{3,Q14})
    x(q) = V3(Float64(q[1]), Float64(q[2]), Float64(q[3]))
    vnorm(vcross(x(Q[2]) - x(Q[1]), x(Q[3]) - x(Q[1]))) >= 1e-4
end

function relo_q(q::Q14, dx::Float64, dy::Float64)::Q14
    ntuple(i -> i == 6 ? q[6] + Float32(dx / 128) : i == 7 ? q[7] + Float32(dy / 128) : q[i], Val(14))
end

function assemble!(bv::Bevel)
    a = bv.a
    S = copy(bv.S)
    plan, npages = a.lm_blend && !isempty(bv.blocks) ? plan_lightmaps!(bv) : (Dict{Int,LmUnit}(), 0)
    newlm, lm_base, lm_stride = isempty(plan) ? (bv.lm, 0, 1) : build_lightmaps(bv, plan, npages)
    mods = Dict{Int,Tuple{Vector{DrawVert},Vector{Int32}}}()
    for f in bv.flist
        f.polys === nothing && continue
        polys = a.merge_polys ? merge_convex(f.polys, f.n * Float64(f.winding)) : f.polys
        inc!(bv, "face_polys_before_merge", length(f.polys))
        inc!(bv, "face_polys_after_merge", length(polys))
        tris = Tri[]
        for P in polys
            append!(tris, triangulate(P))
        end
        if polys !== f.polys
            nn = f.n * Float64(f.winding)
            if any(T -> vdot(vcross(axyz(T[2]) - axyz(T[1]), axyz(T[3]) - axyz(T[1])), nn) < 1e-3, tris)
                polys = f.polys
                tris = Tri[]
                for P in polys
                    append!(tris, triangulate(P))
                end
            end
        end
        inc!(bv, "face_tris", length(tris))
        inc!(bv, "face_poly_verts", sum(length, polys))
        qc = [quant(T) for T in tris]
        qs = [quant(T) for T in f.strip]
        lu = get(plan, f.si, nothing)
        if lu !== nothing
            s0 = bv.S[f.si+1]
            ix, iy, _w, _h = lu.items[findfirst(==(0), lu.bids)]
            dx = Float64(lu.px + ix + 1 - s0.lmx); dy = Float64(lu.py + iy + 1 - s0.lmy)
            qc = [(relo_q(Q[1], dx, dy), relo_q(Q[2], dx, dy), relo_q(Q[3], dx, dy)) for Q in qc]
            for (i, Q) in enumerate(qs)
                bid = Int(f.sblk[i])
                if bid == 0
                    qs[i] = (relo_q(Q[1], dx, dy), relo_q(Q[2], dx, dy), relo_q(Q[3], dx, dy))
                else
                    b = bv.blocks[bid]
                    p = f.spos[i]
                    uv(r, c) = (Float32((b.bx + c - 0.5) / 128), Float32((b.by + r - 0.5) / 128))
                    qs[i] = ntuple(j -> begin
                        l1, l2 = uv(p[2j-1], p[2j])
                        q = Q[j]
                        ntuple(m -> m == 6 ? l1 : m == 7 ? l2 : q[m], Val(14))
                    end, Val(3))
                end
            end
        end
        kc, ks = filter(good, qc), filter(good, qs)
        inc!(bv, "tris_dropped_sliver", length(qc) + length(qs) - length(kc) - length(ks))
        vmap = Dict{Q14,Int}()
        vrows = Q14[]
        idx = Int32[]
        for Q in Iterators.flatten((kc, ks))
            for q in Q
                k = get(vmap, q, 0)
                if k == 0
                    push!(vrows, q)
                    k = length(vrows)
                    vmap[q] = k
                end
                push!(idx, k - 1)
            end
        end
        if isempty(vrows)
            inc!(bv, "faces_emptied_kept_stock"); continue
        end
        if a.surface_type == "face" && length(vrows) > MAX_BEVEL_FACE_VERTS
            inc!(bv, "faces_reverted_over_vert_limit"); continue
        end
        arr = DrawVert[DrawVert(q[1], q[2], q[3], q[4], q[5], q[6], q[7], q[8], q[9], q[10], UInt8(q[11]), UInt8(q[12]), UInt8(q[13]), UInt8(q[14])) for q in vrows]
        s = S[f.si+1]
        inc!(bv, "verts_orphaned", s.nv)
        mods[f.si] = (arr, idx)
        push!(bv.tagged, (f.si, length(kc), length(ks)))
        if lu !== nothing
            ix, iy, _w, _h = lu.items[findfirst(==(0), lu.bids)]
            s = with_lm(s; lmn=lm_base + lm_stride * lu.page, lmx=lu.px + ix + 1, lmy=lu.py + iy + 1)
            S[f.si+1] = s
        end
        if a.surface_type == "tri"
            S[f.si+1] = with_geometry(s; typ=MST_TRISOUP)
            inc!(bv, "surfaces_converted_to_trisoup")
        else
            inc!(bv, "surfaces_kept_planar")
        end
        inc!(bv, "surfaces_modified")
    end
    if a.debug_shader == "uvgrid"
        nsh = length(bv.shd)
        for si in keys(mods)
            S[si+1] = with_shader(S[si+1], nsh)
        end
    end
    out, nv, ni = relayout(bv.bsp, S, bv.V, bv.I, mods)
    if a.debug_shader == "uvgrid"
        nm = codeunits(UVGRID_SHADER)
        nt = ntuple(i -> i <= length(nm) ? nm[i] : 0x00, 64)
        out.lumps[L_SHADER] = to_bytes(vcat(bv.shd, [Shader(nt, Int32(0), Int32(1))]))
        push!(EXTRA_FILES, "textures/codmod_debug/uvgrid.tga" => uvgrid_tga())
        push!(EXTRA_FILES, "scripts/codmod_debug.shader" => Vector{UInt8}(codeunits(UVGRID_SCRIPT)))
    end
    isempty(plan) || (out.lumps[L_LM] = newlm)
    bv.stats["verts_before"], bv.stats["verts_after"] = length(bv.V), nv
    bv.stats["indexes_before"], bv.stats["indexes_after"] = length(bv.I), ni
    out
end

function run!(bv::Bevel; log=true)
    tm = time()
    lap(name) = (log && @printf("  [%6.2fs] %s\n", time() - tm, name); tm = time())
    candidates!(bv); lap("candidates")
    boundary_edges!(bv); lap("boundary edges")
    match_edges!(bv); lap("match edges")
    build_groups!(bv); lap("groups")
    order = Int[]
    for (gid, gr) in enumerate(bv.groups)
        why = prepare!(bv, gr)
        gr.ok = why === nothing
        why === nothing ? push!(order, gid) : inc!(bv, why)
    end
    lap("prepare")
    find_corners!(bv, order); lap("corners")
    find_wall_ends!(bv, order); lap("wall ends")
    find_mitres!(bv, order); lap("mitres")
    bv.a.reject_touched && reject_touched_edges!(bv, order); lap("touched edges")
    drop_overlapping!(bv, order); lap("overlap")
    bv.a.reject_touched && revert_box_vertex_mitres!(bv, order)
    revert_broken_corners!(bv)
    revert_broken_mitres!(bv)
    bv.a.uv_mode == "align" && (orient_components!(bv); align_textures!(bv); seam_resid!(bv))
    bv.a.uv_mode == "align-greedy" && align_textures_greedy!(bv)
    lap("align")
    empty!(bv.end_log); empty!(bv.end_pos); empty!(bv.cap_edges); empty!(bv.tagged)
    for (gid, gr) in enumerate(bv.groups)
        gr.ok || continue
        for e in (0, 1)
            kind = gr.corner[e+1] ? "corner" : gr.mitre[e+1] !== nothing ? "mitre" : gr.wall[e+1] ? "wall" : "taper:" * get(bv.wall_why, (gid, e), "reverted")
            push!(bv.end_log, kind)
            push!(bv.end_pos, gr.P0 + gr.d * (e == 0 ? gr.lo : gr.hi))
        end
    end
    for (gid, gr) in enumerate(bv.groups)
        gr.ok || continue
        for s in copy(gr.fA.keys)
            cut_face!(bv, face(bv, s), gr, gr.wA, 0)
        end
        for s in copy(gr.fB.keys)
            cut_face!(bv, face(bv, s), gr, gr.wB, 1)
        end
    end
    lap("cut faces")
    rebuild_cutverts!(bv)
    used = 0
    for (gid, gr) in enumerate(bv.groups)
        gr.ok || continue
        n = build_strip!(bv, gr, gid)
        inc!(bv, "strip_tris", n)
        inc!(bv, "groups_bevelled")
        inc!(bv, "bevelled_length", gr.hi - gr.lo)
        gr.r < bv.a.radius - 1e-9 && inc!(bv, "groups_adaptive_radius")
        used += 1
    end
    lap("strips")
    for cr in bv.corners
        build_corner!(bv, cr)
    end
    for (gid, gr) in enumerate(bv.groups)
        gr.ok || continue
        for e in (0, 1)
            gr.wall[e+1] || continue
            if !gr.wall_cap[e+1] && !gr.corner[e+1] && cap_uncovered(bv, gr, e)
                gr.wall_cap[e+1] = true
                inc!(bv, "wall_caps_postcut")
            end
            if gr.wall_cap[e+1]
                build_wall_cap!(bv, gr, e, gid)
            else  # end row lies inside the wall face drawn under the ledge: not a crack
                pts = (e == 0 ? gr.row_first : gr.row_last).pts
                for k in 1:length(pts)-1
                    push!(bv.cap_edges, (pts[k], pts[k+1]))
                end
            end
        end
    end
    lap("corners+caps")
    bv.stats["rej_total_groups"] = stat(bv, "groups_candidate") - used
    out = assemble!(bv)
    lap("assemble")
    out
end

function print_stats(bv::Bevel)
    st(k) = (v = stat(bv, k); v == round(v) ? string(Int(v)) : @sprintf("%.3f", v))
    println("--- stats ---")
    println("candidate faces:                ", st("surf_candidates"), " (skipped: shader ", st("surf_skipped_shader"), ", non-planar surfaces ", st("surf_not_planar"), ", bad face fit ", st("surf_skipped_bad_face"), ")")
    println("boundary edges (1 tri in face): ", st("boundary_edges"))
    println("collinear overlapping pairs:    ", st("edge_pairs_collinear_overlap"), " (candidate edges)")
    println("  rejected coplanar:            ", st("rej_coplanar"))
    println("  rejected dihedral angle:      ", st("rej_angle"))
    println("  rejected concave:             ", st("rej_concave"), " (pair level)")
    println("  convex pairs kept:            ", st("pairs_convex"))
    println("edge groups (merged runs):      ", st("groups_candidate"))
    println("  rejected short (< min-len):   ", st("rej_short"))
    println("  rejected thin (r < min-radius):", st("rej_thin_face"))
    println("  rejected concave (group):     ", st("rej_concave_group"))
    @printf("  bevelled groups:              %s  total length %.0f units\n", st("groups_bevelled"), stat(bv, "bevelled_length"))
    if stat(bv, "align_edges") > 0
        @printf("align (global LS): %s edges, %s skipped as cycle-inconsistent (residual > 0.05 period), %.1f%% of seam length within 0.05 period; other shader %s, scale %s, drifting mapping %s, same component %s\n",
                st("align_edges"), st("align_cycle_skips"), 100 * stat(bv, "align_len_good") / max(1.0, stat(bv, "align_len_total")), st("align_other_shader"), st("align_scale"), st("align_drift"), st("align_same_component"))
    end
    if stat(bv, "align_shifted") > 0 || stat(bv, "align_drift") > 0 || stat(bv, "align_scale") > 0
        @printf("align: shifted %s components (%s faces, mean |shift| %.3f period); skipped: other shader %s, scale %s, drifting mapping %s\n", st("align_shifted"), st("align_faces"),
                stat(bv, "align_shift_sum") / max(1, stat(bv, "align_shifted")), st("align_other_shader"), st("align_scale"), st("align_drift"))
    end
    println("uv pairs: morph ", st("uv_morph_pairs"), ", seam (different shader) ", st("uv_seam_pairs_other_shader"), ", seam (scale ratio > 1.5 fallback) ", st("uv_seam_pairs_scale_fallback"))
    println("face tris ", st("face_tris"), " from ", st("face_poly_verts"), " polygon verts")
    println("face polygons: ", st("face_polys_before_merge"), " pieces -> ", st("face_polys_after_merge"), " after merging")
    print_class_table(bv)
    println("strip rows: ", st("strip_rows_candidate"), " candidates, ", st("strip_rows_kept"), " kept")
    println("adaptive radius (smaller than --radius): ", st("groups_adaptive_radius"), " of ", st("groups_bevelled"), " runs")
    println("box corners: found ", st("corners_found"), ", patched ", st("corner_patches"), " (", st("corner_patch_tris"), " tris), reverted to taper ", st("corners_reverted"),
            "; rejected: not 3 runs ", st("corner_rej_not_three_runs"), ", not a box vertex ", st("corner_rej_not_a_box_vertex"), ", not orthogonal ", st("corner_rej_not_orthogonal"), ", skewed ", st("corner_rej_skewed"))
    println("wall ends: ", st("wall_ends"), " (end-row mismatch >0.3u ", st("wall_end_row_mismatch"), "; under-wall, no cap needed ", st("wall_ends_under"), "; caps ", st("wall_caps"), ", ", st("wall_cap_tris"),
            " tris), rejected: no wall plane ", st("wall_rej_no_plane"), ", no hole boundary ", st("wall_rej_no_hole"))
    cnt = Dict{String,Int}()
    for k in bv.end_log
        cnt[k] = get(cnt, k, 0) + 1
    end
    println("run ends of bevelled runs: ", cnt, "; wall flags reverted to taper (overlap/coverage) ", st("wall_ends_reverted_overlap"))
    println("mitres: ", st("mitres_found"), " of ", st("mitre_cand"), " candidate bends (rejected: planes ", st("mitre_rej_planes"), ", radius/angle ", st("mitre_rej_radius_angle"), ", not a reflex L ", st("mitre_rej_not_reflex_L"),
            "); reverted: overlap ", st("mitres_reverted_overlap"), ", partner ", st("mitres_reverted_partner"), "; failed with mitre: coverage ", st("mitre_fail_rej_face_coverage"), ", overlap ", st("mitre_fail_rej_overlap_run"),
            "; asymmetric ", st("mitre_asymmetric"), ", corner vertex missing ", st("mitre_corner_vertex_missing"))
    println("strip triangles added:          ", st("strip_tris"), "  (degenerate skipped ", st("strip_tris_degenerate_skipped"), ", centre mismatches ", st("strip_center_mismatch"), ")")
    println("P8/P9: wrapped different-shader intervals ", st("wrap_intervals"), ", offset-ramped strip vertices ", st("strip_offset_ramped"))
    println("  rejected cut region off face: ", st("rej_face_coverage"))
    println("  rejected, foreign surface touches edge: ", st("rej_touched_edge"), "; diagonal contact: ", st("rej_diagonal_contact"), "; mitres reverted at box vertex: ", st("mitre_reverted_box_vertex"))
    println("  rejected overlapping runs:    ", st("rej_overlap_run"))
    println("  faces reverted (>1024 verts): ", st("faces_reverted_over_vert_limit"), ", fully cut away (kept stock) ", st("faces_emptied_kept_stock"))
    println("surfaces modified:              ", st("surfaces_modified"), " (kept planar ", st("surfaces_kept_planar"), ", converted to trisoup ", st("surfaces_converted_to_trisoup"), ")")
    println("drawverts:   ", st("verts_before"), " -> ", st("verts_after"), " (compacted: stock ranges of rewritten surfaces dropped, ", st("verts_orphaned"), " verts)")
    println("drawindexes: ", st("indexes_before"), " -> ", st("indexes_after"))
end
