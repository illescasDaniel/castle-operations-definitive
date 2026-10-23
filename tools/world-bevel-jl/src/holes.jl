# --hole-scan: topological post-check of the final rounded runs. Rounding a convex edge removes a wedge of solid at the
# edge; the wedge is only invisible-safe when nothing else needs it. This pass is independent of the rejection rules in
# `reject_touched_edges!` (it works on triangles, not vertices, and on the final state of `bv.groups`), so it can catch
# their gaps. Categories:
#   touched   the boundary edge of a foreign original surface (not on the run's faces, not continuing one of its planes) lies on
#             the edge line strictly inside a rounded run (a surface merely passing through the line leaves no slit)
#   tee       same, but the foreign boundary edge crosses the line without a vertex on it (a T junction; whether this opens
#             a visible slit is unverified, the rejection rules do not cover it)
#   diagonal  two rounded runs on one edge line, overlapping, with unrelated faces (two solids touching diagonally)
#   overlap   two rounded runs on one edge line, overlapping, sharing a face (double cut)
#   mitre3    a mitred run end whose vertex has no third rounded run through it (box vertex with a sharp third edge)
#   corner3   a box-corner run end with fewer than three rounded runs through the vertex
# Debug: `--no-reject-touched` (Opts.reject_touched = false) skips the rejection rules so the detector can be tested.

struct ScanHit
    cat::Symbol
    gid::Int
    p::V3
    note::String
end

# distance between segments [p0,p1] and [q0,q1] (closest points), plus the parameter on the first one
function seg_seg(p0::V3, p1::V3, q0::V3, q1::V3)
    u = p1 - p0; v = q1 - q0; w = p0 - q0
    a = vdot(u, u); b = vdot(u, v); c = vdot(v, v); d = vdot(u, w); e = vdot(v, w)
    D = a * c - b * b
    sN = D < 1e-12 ? 0.0 : b * e - c * d
    sD = D < 1e-12 ? 1.0 : D
    tN = D < 1e-12 ? e : a * e - b * d
    tD = D < 1e-12 ? c : D
    if D >= 1e-12
        if sN < 0; sN = 0.0; tN = e; tD = c
        elseif sN > sD; sN = sD; tN = e + b; tD = c end
    end
    if tN < 0
        tN = 0.0
        if -d < 0; sN = 0.0 elseif -d > a; sN = sD else sN = -d; sD = a end
    elseif tN > tD
        tN = tD
        if (-d + b) < 0; sN = 0.0 elseif (-d + b) > a; sN = sD else sN = -d + b; sD = a end
    end
    sc = abs(sN) < 1e-12 ? 0.0 : sN / sD
    tc = abs(tN) < 1e-12 ? 0.0 : tN / tD
    vnorm(w + u * sc - v * tc), sc
end

function hole_scan(bv::Bevel; maxprint=12)
    cell = 32.0; eps = 0.25
    # Boundary edges of all drawn planar original surfaces (edges used by one triangle of the surface), in a grid. Only a
    # surface BOUNDARY on the edge line leaves a slit when the wedge is removed; a surface passing through the line does not.
    ea = V3[]; eb = V3[]; en = V3[]; esf = Int[]
    grid = Dict{NTuple{3,Int},Vector{Int32}}()
    q16(p::V3) = (round(Int, p.x * 16), round(Int, p.y * 16), round(Int, p.z * 16))
    for (si, s) in enumerate(bv.S)
        s.typ == MST_PLANAR || continue
        (bv.shd[s.shader+1].sf & SURF_NODRAW) != 0 && continue
        cnt = Dict{Tuple{NTuple{3,Int},NTuple{3,Int}},Tuple{Int,V3,V3,V3}}()
        for k in 0:3:s.ni-3
            v = ntuple(j -> bv.V[s.fv+bv.I[s.fi+k+j]+1], 3)
            p = ntuple(j -> V3(v[j].x, v[j].y, v[j].z), 3)
            vnorm(vcross(p[2] - p[1], p[3] - p[1])) < 1e-9 && continue
            nn = V3(v[1].nx, v[1].ny, v[1].nz)
            for (u, w) in ((p[1], p[2]), (p[2], p[3]), (p[3], p[1]))
                ku, kw = q16(u), q16(w)
                ku == kw && continue
                key = ku < kw ? (ku, kw) : (kw, ku)
                c0 = get(cnt, key, (0, u, w, nn))
                cnt[key] = (c0[1] + 1, c0[2], c0[3], c0[4])
            end
        end
        for (c, u, w, nn) in values(cnt)
            c == 1 || continue
            push!(ea, u); push!(eb, w); push!(en, nn); push!(esf, si - 1)
            id = Int32(length(ea))
            lo = (min(u.x, w.x), min(u.y, w.y), min(u.z, w.z)) .- eps
            hi = (max(u.x, w.x), max(u.y, w.y), max(u.z, w.z)) .+ eps
            c0 = floor.(Int, lo ./ cell); c1 = floor.(Int, hi ./ cell)
            for x in c0[1]:c1[1], y in c0[2]:c1[2], z in c0[3]:c1[3]
                push!(get!(Vector{Int32}, grid, (x, y, z)), id)
            end
        end
    end
    hits = ScanHit[]
    oks = [gid for (gid, g) in enumerate(bv.groups) if g.ok]
    # --- touched: boundary edge of a foreign surface on the edge line, strictly inside the run
    for gid in oks
        gr = bv.groups[gid]
        gr.hi - gr.lo > 2 * gr.r || continue
        a = gr.P0 + gr.d * (gr.lo + 0.5); b = gr.P0 + gr.d * (gr.hi - 0.5)
        seen = Set{Int32}()
        L = vnorm(b - a)
        found = false
        for t in 0.0:4.0:L
            pt = a + gr.d * t
            for id in get(grid, (floor(Int, pt.x / cell), floor(Int, pt.y / cell), floor(Int, pt.z / cell)), Int32[])
                id in seen && continue
                push!(seen, id)
                sf = esf[id]
                (sf in gr.fA.keys || sf in gr.fB.keys) && continue
                n = en[id]
                (vdot(n, gr.nA) > 0.99 || vdot(n, gr.nB) > 0.99) && continue
                ev = eb[id] - ea[id]
                hp = nothing
                if vnorm(vcross(ev, gr.d)) < 1e-6 * vnorm(ev)       # parallel: collinear overlap
                    w = ea[id] - a
                    q = w - gr.d * vdot(w, gr.d)
                    if vdot(q, q) <= eps * eps
                        t0 = vdot(ea[id] - a, gr.d); t1 = vdot(eb[id] - a, gr.d)
                        lo_, hi_ = max(min(t0, t1), 0.0), min(max(t0, t1), L)
                        hi_ - lo_ > 0.5 && (hp = a + gr.d * (0.5 * (lo_ + hi_)))
                    end
                else
                    dd, sc = seg_seg(a, b, ea[id], eb[id])
                    dd <= eps && sc > 1e-6 && sc < 1 - 1e-6 && (hp = a + (b - a) * sc)
                end
                hp === nothing && continue
                onl(p) = (w = p - a; t = vdot(w, gr.d); q = w - gr.d * t; vdot(q, q) <= eps * eps && t > 0 && t < L)
                vtx = onl(ea[id]) || onl(eb[id])
                push!(hits, ScanHit(vtx ? :touched : :tee, gid, hp, @sprintf("surf %d boundary edge %s, %.1f from run start (run length %.1f)", sf, vtx ? "with a vertex on the line" : "crossing the line", vdot(hp - gr.P0, gr.d) - gr.lo, gr.hi - gr.lo)))
                found = true
                break
            end
            found && break
        end
    end
    # --- diagonal / overlap: runs on one line
    for (i, ia) in enumerate(oks), ib in oks[i+1:end]
        ga, gb = bv.groups[ia], bv.groups[ib]
        abs(vdot(ga.d, gb.d)) > 0.9999 || continue
        w = gb.P0 - ga.P0
        q = w - ga.d * vdot(w, ga.d)
        vdot(q, q) < 0.25 || continue
        ta0, ta1 = sort([vdot(ga.P0 + ga.d * ga.lo, ga.d), vdot(ga.P0 + ga.d * ga.hi, ga.d)])
        tb0, tb1 = sort([vdot(gb.P0 + gb.d * gb.lo, ga.d), vdot(gb.P0 + gb.d * gb.hi, ga.d)])
        ov = min(ta1, tb1) - max(ta0, tb0)
        ov > 1.0 || continue
        share = !isempty(intersect(ga.fA.keys, gb.fA.keys)) || !isempty(intersect(ga.fA.keys, gb.fB.keys)) ||
                !isempty(intersect(ga.fB.keys, gb.fA.keys)) || !isempty(intersect(ga.fB.keys, gb.fB.keys))
        pm = ga.P0 + ga.d * (0.5 * (max(ta0, tb0) + min(ta1, tb1)) - vdot(ga.P0, ga.d))
        share || vdot(unit(ga.nA + ga.nB), unit(gb.nA + gb.nB)) < -0.05 || continue   # same-side wedges: not a touch
        push!(hits, ScanHit(share ? :overlap : :diagonal, ia, pm, "with run $ib, overlap $(round(ov, digits=1))"))
    end
    # --- mitre3 / corner3: run ends that rely on other rounded runs at the vertex
    for gid in oks
        gr = bv.groups[gid]
        for e in (0, 1)
            mt = gr.mitre[e+1]
            (mt !== nothing || gr.corner[e+1]) || continue
            pe = gr.P0 + gr.d * (e == 0 ? gr.lo : gr.hi)
            if mt !== nothing
                # only box vertices (three mutually orthogonal faces) need a third rounded edge; other bends are geometry dependent
                pg = bv.groups[mt.partner[1]]
                shared = abs(vdot(gr.nB, pg.nB)) > 0.99 || abs(vdot(gr.nB, pg.nA)) > 0.99 ? gr.nB : gr.nA
                n1 = shared === gr.nB ? gr.nA : gr.nB
                n2 = abs(vdot(shared, pg.nA)) > 0.99 ? pg.nB : pg.nA
                abs(vdot(n1, n2)) < 0.1 || continue
            end
            dirs = V3[]
            for g3i in oks
                g3 = bv.groups[g3i]
                w = pe - g3.P0
                t = vdot(w, g3.d)
                q = w - t * g3.d
                (vdot(q, q) < 0.09 && t > g3.lo - 0.3 && t < g3.hi + 0.3) || continue
                any(d -> abs(vdot(d, g3.d)) > 0.999, dirs) || push!(dirs, g3.d)
            end
            if length(dirs) < 3
                push!(hits, ScanHit(mt !== nothing ? :mitre3 : :corner3, gid, pe, "end $e, $(length(dirs)) rounded edge direction(s) at the vertex"))
            end
        end
    end
    cats = (:touched, :tee, :diagonal, :overlap, :mitre3, :corner3)
    @printf("hole-scan: %d rounded runs checked; uncovered wedges: %s\n", length(oks),
            join(["$c $(count(h -> h.cat == c, hits))" for c in cats], ", "))
    for c in cats
        sel = filter(h -> h.cat == c, hits)
        for h in first(sel, maxprint)
            @printf("  %s run %d at (%.1f %.1f %.1f): %s\n", h.cat, h.gid, h.p.x, h.p.y, h.p.z, h.note)
        end
        length(sel) > maxprint && @printf("  ... %d more %s (WB_SCAN_DUMP=file.tsv lists all)\n", length(sel) - maxprint, c)
    end
    dump = get(ENV, "WB_SCAN_DUMP", "")
    if !isempty(dump)
        open(dump, "w") do io
            println(io, "category\trun\tx\ty\tz\tnote")
            for h in hits
                @printf(io, "%s\t%d\t%.2f\t%.2f\t%.2f\t%s\n", h.cat, h.gid, h.p.x, h.p.y, h.p.z, h.note)
            end
        end
    end
    hits
end
