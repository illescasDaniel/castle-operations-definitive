# --hole-scan: ray-based hole finder. Around every bevelled run, rays aimed at points of the ORIGINAL faces next to the
# edge are cast against the original and the rewritten triangle sets (front faces only, like the renderer). A ray that
# hits the original at its target but whose new hit is missing or far from the edge line goes through a gap.

struct TriSet
    a::Vector{V3}; e1::Vector{V3}; e2::Vector{V3}
    cell::Float64
    grid::Dict{NTuple{3,Int},Vector{Int32}}
end

function triset(b::Bsp; cell=32.0)
    V = verts(b); I = indexes(b); S = surfaces(b); Sh = shaders(b)
    A = V3[]; E1 = V3[]; E2 = V3[]
    grid = Dict{NTuple{3,Int},Vector{Int32}}()
    for s in S
        (s.typ == MST_PLANAR || s.typ == MST_TRISOUP) || continue
        sh = Sh[s.shader+1]
        (sh.sf & SURF_NODRAW) != 0 && continue
        for k in 0:3:s.ni-3
            v = ntuple(j -> V[s.fv+I[s.fi+k+j]+1], 3)
            p = ntuple(j -> V3(v[j].x, v[j].y, v[j].z), 3)
            e1 = p[2] - p[1]; e2 = p[3] - p[1]
            vnorm(vcross(e1, e2)) < 1e-9 && continue
            push!(A, p[1]); push!(E1, e1); push!(E2, e2)
            id = Int32(length(A))
            lo = (min(p[1].x, p[2].x, p[3].x), min(p[1].y, p[2].y, p[3].y), min(p[1].z, p[2].z, p[3].z))
            hi = (max(p[1].x, p[2].x, p[3].x), max(p[1].y, p[2].y, p[3].y), max(p[1].z, p[2].z, p[3].z))
            c0 = floor.(Int, lo ./ cell); c1 = floor.(Int, hi ./ cell)
            for x in c0[1]:c1[1], y in c0[2]:c1[2], z in c0[3]:c1[3]
                push!(get!(Vector{Int32}, grid, (x, y, z)), id)
            end
        end
    end
    TriSet(A, E1, E2, cell, grid)
end

# nearest hit distance along o + t*dir, t in (0, tmax] (front faces only, or any face with anyface=true, which then
# also returns whether the hit was a front face); Inf when none. Cells are walked with a 3D DDA.
function cast(ts::TriSet, o::V3, dir::V3, tmax::Float64; anyface=false)
    best = Inf; bfront = true
    cs = ts.cell
    ix = floor(Int, o.x / cs); iy = floor(Int, o.y / cs); iz = floor(Int, o.z / cs)
    sx = dir.x > 0 ? 1 : -1; sy = dir.y > 0 ? 1 : -1; sz = dir.z > 0 ? 1 : -1
    nxt(i, s, p, dd) = dd == 0 ? Inf : (((s > 0 ? i + 1 : i) * cs) - p) / dd
    tx = nxt(ix, sx, o.x, dir.x); ty = nxt(iy, sy, o.y, dir.y); tz = nxt(iz, sz, o.z, dir.z)
    dx = dir.x == 0 ? Inf : cs / abs(dir.x); dy = dir.y == 0 ? Inf : cs / abs(dir.y); dz = dir.z == 0 ? Inf : cs / abs(dir.z)
    while true
        lst = get(ts.grid, (ix, iy, iz), nothing)
        if lst !== nothing
            for id in lst
                e1 = ts.e1[id]; e2 = ts.e2[id]
                pv = vcross(dir, e2)
                det = vdot(e1, pv)
                (anyface ? abs(det) < 1e-12 : det >= -1e-12) && continue
                inv = 1 / det
                tv = o - ts.a[id]
                u = vdot(tv, pv) * inv
                (u < -1e-9 || u > 1 + 1e-9) && continue
                q = vcross(tv, e1)
                v = vdot(dir, q) * inv
                (v < -1e-9 || u + v > 1 + 1e-9) && continue
                t2 = vdot(e2, q) * inv
                t2 > 1e-6 && t2 < best && (best = t2; bfront = det < 0)
            end
        end
        tn = min(tx, ty, tz)
        (best <= tn || tn > tmax) && break
        if tx == tn
            ix += sx; tx += dx
        elseif ty == tn
            iy += sy; ty += dy
        else
            iz += sz; tz += dz
        end
    end
    anyface ? (best <= tmax ? best : Inf, bfront) : (best <= tmax ? best : Inf)
end

function hole_scan(bv::Bevel, orig::Bsp, new::Bsp; step=5.0, maxprint=100000)
    to = triset(orig); tn = triset(new)
    # orientation sanity check: a front-facing hit on a stock planar face from along its normal must exist
    res = Tuple{Int,V3,V3,Float64,String}[]       # gid, target, origin, new hit dist, note
    nrays = 0; nbad = 0
    badg = Dict{Int,Int}()
    allbad = Tuple{Int,V3,V3,Int,Float64,String}[]
    first_bad = Dict{Int,Tuple{Int,V3,V3,Float64,String}}()
    for (gid, gr) in enumerate(bv.groups)
        gr.ok || continue
        r = gr.r
        bis = unit(gr.nA + gr.nB)
        for t in (gr.lo+gr.tap+1.0):step:(gr.hi-gr.tap-1.0)
            e = gr.P0 + gr.d * t
            for (w, n, other, wo) in ((gr.wA, gr.nA, gr.nB, gr.wB), (gr.wB, gr.nB, gr.nA, gr.wA))
                for s in (0.15, 0.5, 1.0, 1.4)
                    T = e + w * (s * r) + n * 0.02
                    for (u0, L) in ((n, 14.0), (bis, 14.0), (unit(n + w * 0.58), 20.0), (unit(n + w * 1.43), 30.0), (unit(n + w * 3.7), 40.0),
                                    (unit(n + w * 0.58 + gr.d * 0.4), 20.0), (unit(n + w * 0.58 - gr.d * 0.4), 20.0))
                        O = T + u0 * L
                        dir = unit(T - O)
                        dist = vnorm(T - O)
                        d0 = cast(to, O, dir, dist + 1.0)
                        (d0 > dist - 0.5 && d0 < dist + 0.5) || continue   # original must show this face point
                        nrays += 1
                        d1 = cast(tn, O, dir, dist + 200.0)
                        ok = false
                        if d1 < Inf
                            H = O + dir * d1
                            ok = vnorm(H - T) < 1.5 * r + 1.0
                        end
                        kind = "ok"
                        if !ok
                            # The ray passes the removed tip. That is legal (silhouette) when the air it enters is the same
                            # air as the viewer's: P1 (before T) and P2 (where it leaves the original solid) must be joined
                            # in the ORIGINAL by an unobstructed path around the tip via C on the edge bisector.
                            # A ray that misses the rounded surface near T is fine when it then runs through air (silhouette
                            # past the rounded tip): it meets a front face next. If the next hit is a back face, or nothing, the
                            # ray went through solid: a gap.
                            d2, fr = cast(tn, T + dir * 0.01, dir, 6000.0; anyface=true)
                            ok = d2 < Inf && fr
                            kind = d2 == Inf ? "void" : "back"
                        end
                        if !ok
                            nbad += 1
                                badg[gid] = get(badg, gid, 0) + 1
                            push!(allbad, (gid, T, O, 0, s, kind)); haskey(first_bad, gid) || (first_bad[gid] = (gid, T, O, d1, kind))
                                                    end
                    end
                end
            end
        end
    end
    @printf("hole-scan: %d rays at original face points near %d bevelled runs; %d go through gaps (%d runs)\n", nrays, count(g -> g.ok, bv.groups), nbad, length(badg))
    # report: worst runs, with a camera that reproduces the ray
    byg = sort!(collect(badg), by=x -> -x[2])
    for (gid, n) in first(byg, maxprint)
        gr = bv.groups[gid]
        _, T, O, d1, kind = first_bad[gid]
        dir = unit(T - O)
        yaw = rad2deg(atan(dir.y, dir.x)); pitch = rad2deg(-asin(clamp(dir.z, -1, 1)))
        @printf("  group %d: %d bad rays; run %.0f..%.0f along d=(%.2f %.2f %.2f) at (%.1f %.1f %.1f) r=%.2f ends[corner %s mitre %s wall %s]; new hit %s (%s) target (%.1f %.1f %.1f)\n    setviewpos %.1f %.1f %.1f %.1f %.1f\n",
                gid, n, gr.lo, gr.hi, gr.d.x, gr.d.y, gr.d.z, gr.P0.x, gr.P0.y, gr.P0.z, gr.r,
                string(gr.corner), string(map(m -> m !== nothing, gr.mitre)), string(gr.wall), isfinite(d1) ? @sprintf("%.1f", d1) : "none", kind, T.x, T.y, T.z,
                O.x, O.y, O.z, yaw, pitch)
    end
    dump = get(ENV, "WB_SCAN_DUMP", "")
    if !isempty(dump)
        open(dump, "w") do io
            for (gid, T, O, ui, s, kind) in allbad
                @printf(io, "%d\t%.2f %.2f %.2f\t%.2f %.2f %.2f\t%d\t%.2f\t%s\n", gid, T.x, T.y, T.z, O.x, O.y, O.z, ui, s, kind)
            end
        end
    end
    badg
end
