# Checks and exports: --roundtrip, --validate, --obj/--region, --dump-rej (ports of cmd_roundtrip / validate / write_obj).

"Names of all maps with a maps/NAME.bsp in run/main/*.pk3."
function all_maps(root)
    names = Set{String}()
    for p in pak_list(root)
        for e in zip_entries(p)
            m = match(r"^maps/([^/]+)\.bsp$", e.name)
            m === nothing || push!(names, String(m.captures[1]))
        end
    end
    sort!(collect(names))
end

"Parse + write must reproduce every map byte for byte."
function cmd_roundtrip(root, all::Bool, map::String)
    names = all ? all_maps(root) : [map]
    bad = 0
    for n in names
        data = find_bsp(root, n)
        ok = try
            write_bsp(Bsp(data)) == data
        catch e
            e isa ErrorException || rethrow()
            println("  $n: SKIP ($(e.msg))")
            continue
        end
        bad += !ok
        println("  $n: ", ok ? "identical" : "MISMATCH", " ($(length(data)) bytes)")
    end
    println("roundtrip: $(length(names) - bad)/$(length(names)) byte-identical")
    bad == 0
end

const RegionBox = NTuple{6,Float64}

"(positions, surface index) of every triangle of the planar and trisoup world surfaces (centroid inside `region` when given)."
function world_tris(b::Bsp, region::Union{Nothing,RegionBox})
    V, I, S, m0 = verts(b), indexes(b), surfaces(b), models(b)[1]
    P = NTuple{3,V3}[]
    SI = Int[]
    for si in Int(m0.fs):Int(m0.fs + m0.ns) - 1
        s = S[si+1]
        (s.typ == MST_PLANAR || s.typ == MST_TRISOUP) || continue
        for k in 0:Int(s.ni)÷3-1
            tri = ntuple(j -> (v = V[s.fv + I[s.fi + 3k + j] + 1]; V3(v.x, v.y, v.z)), 3)
            if region !== nothing
                c = (tri[1] + tri[2] + tri[3]) / 3
                (region[1] <= c.x <= region[4] && region[2] <= c.y <= region[5] && region[3] <= c.z <= region[6]) || continue
            end
            push!(P, tri); push!(SI, si)
        end
    end
    P, SI
end

function write_obj(path, b::Bsp, region)
    P, _ = world_tris(b, region)
    open(path, "w") do io
        println(io, "# $(length(P)) triangles")
        for T in P, p in T
            @printf(io, "v %.4f %.4f %.4f\n", p.x, p.y, p.z)
        end
        for k in 0:length(P)-1
            println(io, "f $(3k + 1) $(3k + 2) $(3k + 3)")
        end
    end
    println("$path: $(length(P)) triangles")
end

"--dump-rej: kinds and positions of run ends / rejected box vertices inside the box."
function dump_rej(bv::Bevel, box::RegionBox)
    inbox(p) = box[1] <= p.x <= box[4] && box[2] <= p.y <= box[5] && box[3] <= p.z <= box[6]
    sel = Tuple{String,V3}[x for x in bv.rej_log if inbox(x[2])]
    append!(sel, [(bv.end_log[i], bv.end_pos[i]) for i in eachindex(bv.end_log) if inbox(bv.end_pos[i])])
    cnt = Dict{String,Int}()
    for (k, _) in sel
        cnt[k] = get(cnt, k, 0) + 1
    end
    println("run ends in box: ", cnt)
    for (k, p) in sort(sel, by=x -> (x[1], x[2].x, x[2].y, x[2].z))
        @printf("   %-7s [%.1f %.1f %.1f]\n", k, p.x, p.y, p.z)
    end
end

const QSTEP = 2e-3
qpt(p::V3) = (round(Int64, p.x / QSTEP), round(Int64, p.y / QSTEP), round(Int64, p.z / QSTEP))
qedge(a::V3, b::V3) = (ka = qpt(a); kb = qpt(b); ka <= kb ? (ka, kb) : (kb, ka))
f32(p::V3) = V3(Float64(Float32(p.x)), Float64(Float32(p.y)), Float64(Float32(p.z)))

"Checks on the modified BSP; returns ([(name, ok, detail)], unmatched strip edges)."
function validate(orig::Bsp, new::Bsp, bv::Bevel)
    res = Tuple{String,Bool,String}[]
    V, I, S = verts(new), indexes(new), surfaces(new)
    S0 = surfaces(orig)
    bad_range = 0
    for s in S
        fv, nv, fi, ni = Int(s.fv), Int(s.nv), Int(s.fi), Int(s.ni)
        if s.typ == MST_PLANAR || s.typ == MST_TRISOUP
            bad = fv + nv > length(V) || fi + ni > length(I) || ni % 3 != 0
            if !bad && ni > 0
                ix = view(I, fi+1:fi+ni)
                bad = minimum(ix) < 0 || maximum(ix) >= nv
            end
            bad_range += bad
        else
            bad_range += (fv + nv > length(V) || fi + ni > length(I))
        end
    end
    push!(res, ("indices/vert ranges valid for all surfaces", bad_range == 0, "$bad_range bad"))
    push!(res, ("surface count unchanged", length(S) == length(S0), "$(length(S0)) -> $(length(S))"))
    nonfin = count(v -> !(isfinite(v.x) && isfinite(v.y) && isfinite(v.z) && isfinite(v.s) && isfinite(v.t) &&
                          isfinite(v.l1) && isfinite(v.l2) && isfinite(v.nx) && isfinite(v.ny) && isfinite(v.nz)), V)
    push!(res, ("no NaN/inf in verts", nonfin == 0, ""))
    mod = Dict(si => (c, ns) for (si, c, ns) in bv.tagged)
    lmblend = bv.a.lm_blend && orig.lumps[L_LM] != new.lumps[L_LM]
    same = length(S) == length(S0) && all(i -> S[i].shader == S0[i].shader && S[i].fog == S0[i].fog &&
                                              (S[i].lmn == S0[i].lmn || (lmblend && haskey(mod, i - 1))), eachindex(S))
    push!(res, ("shader/fog/lightmapNum unchanged", same, lmblend ? "(lightmap-blended surfaces may move to appended pages)" : ""))
    other = all(i -> new.lumps[i] == orig.lumps[i] || (i == L_LM && lmblend && length(new.lumps[i]) >= length(orig.lumps[i])), setdiff(1:NLUMPS, (L_VERT, L_INDEX, L_SURF)))
    push!(res, ("all other lumps byte-identical", other, lmblend ? "(lightmap lump only appended to)" : ""))
    degen = lm_out = nrm_bad = n_strip = ties = 0
    strip_edges, face_edges = Dict{Tuple{NTuple{3,Int64},NTuple{3,Int64}},Int}(), Dict{Tuple{NTuple{3,Int64},NTuple{3,Int64}},Int}()
    face_segs = Tuple{V3,V3}[]
    tol = 1e-6
    for (si, (nclip, nstrip)) in mod
        s = S[si+1]
        f = face(bv, si)
        vs = view(V, Int(s.fv)+1:Int(s.fv + s.nv))
        ix = [Int(I[Int(s.fi) + k + 1]) + 1 for k in 0:Int(s.ni)-1]
        ntri = length(ix) ÷ 3
        pos(k) = (v = vs[k]; V3(v.x, v.y, v.z))
        nrm(k) = (v = vs[k]; V3(v.nx, v.ny, v.nz))
        cr = [vcross(pos(ix[3t-1]) - pos(ix[3t-2]), pos(ix[3t]) - pos(ix[3t-2])) for t in 1:ntri]
        degen += count(c -> vnorm(c) < 1e-4, cr)
        if s.lmn >= 0
            lo = (s.lmx / 128.0 - tol, s.lmy / 128.0 - tol)
            hi = ((s.lmx + s.lmw) / 128.0 + tol, (s.lmy + s.lmh) / 128.0 + tol)
            if lmblend  # strip vertices live in appended lightmap blocks: check the clipped-face vertices against the rect, the rest against the page
                clipv = falses(length(vs))
                for t in 1:nclip, j in 0:2
                    clipv[ix[3t-2+j]] = true
                end
                for (k, v) in enumerate(vs)
                    if clipv[k]
                        lm_out += (v.l1 < lo[1] || v.l1 > hi[1] || v.l2 < lo[2] || v.l2 > hi[2])
                    else
                        lm_out += (v.l1 < -tol || v.l1 > 1 + tol || v.l2 < -tol || v.l2 > 1 + tol)
                    end
                end
            else
                for v in vs
                    lm_out += (v.l1 < lo[1] || v.l1 > hi[1] || v.l2 < lo[2] || v.l2 > hi[2])
                end
            end
        end
        if nstrip > 0
            for t in ntri-nstrip+1:ntri
                navg = nrm(ix[3t-2]) + nrm(ix[3t-1]) + nrm(ix[3t])
                d = vdot(cr[t], navg) * f.winding
                nrm_bad += (d <= 0 && vnorm(cr[t]) > 0.05)
            end
            n_strip += nstrip
        end
        for t in 1:nclip
            g = vdot(cr[t], f.n) * f.winding
            ties += (g < -1e-6 && vnorm(cr[t]) > 0.05)
        end
        for t in 1:ntri
            tgt = t > ntri - nstrip ? strip_edges : face_edges
            for (a_, b_) in ((0, 1), (1, 2), (2, 0))
                pa, pb = pos(ix[3t-2+a_]), pos(ix[3t-2+b_])
                vnorm(pa - pb) < 1e-4 && continue
                key = qedge(pa, pb)
                tgt[key] = get(tgt, key, 0) + 1
                tgt === face_edges && push!(face_segs, (pa, pb))
            end
        end
    end
    push!(res, ("no degenerate triangles in modified surfaces", degen == 0, "$degen degenerate"))
    push!(res, ("lightmap coords inside each surface rect (+-1e-6)", lm_out == 0, "$lm_out verts outside"))
    push!(res, ("strip triangle normals agree with vertex normals", nrm_bad == 0, "$nrm_bad/$n_strip flipped"))
    push!(res, ("clipped face triangles keep original winding", ties == 0, "$ties flipped"))
    open_edges = [e for (e, c) in strip_edges if c == 1]
    capq = Set(qedge(f32(pa), f32(pb)) for (pa, pb) in bv.cap_edges)
    n_cap_open = count(e -> e in capq && !haskey(face_edges, e), open_edges)
    open_edges = filter(e -> !(e in capq) || haskey(face_edges, e), open_edges)
    exact = count(e -> haskey(face_edges, e), open_edges)
    unmatched = filter(e -> !haskey(face_edges, e), open_edges)
    CELL = 8.0
    cell(p::V3) = (floor(Int, p.x / CELL), floor(Int, p.y / CELL), floor(Int, p.z / CELL))
    grid = Dict{NTuple{3,Int},Vector{Int}}()
    for (k, (pa, pb)) in enumerate(face_segs)
        n = max(2, floor(Int, vnorm(pb - pa) / 4) + 2)
        cs = Set(cell(pa + (pb - pa) * ((i - 1) / (n - 1))) for i in 1:n)
        for c in cs
            push!(get!(grid, c, Int[]), k)
        end
    end
    partial = tiny = 0
    gaps = Tuple{V3,V3}[]
    for e in unmatched
        pa = V3(e[1][1] * QSTEP, e[1][2] * QSTEP, e[1][3] * QSTEP)
        pb = V3(e[2][1] * QSTEP, e[2][2] * QSTEP, e[2][3] * QSTEP)
        m = (pa + pb) * 0.5
        c0 = cell(m)
        cand = Set{Int}()
        for dx in -1:1, dy in -1:1, dz in -1:1
            union!(cand, get(grid, (c0[1] + dx, c0[2] + dy, c0[3] + dz), Int[]))
        end
        found = false
        for k in cand
            a_, b_ = face_segs[k]
            ab = b_ - a_
            tt = min(1.0, max(0.0, vdot(m - a_, ab) / max(vdot(ab, ab), 1e-12)))
            if vnorm(a_ + ab * tt - m) < 5e-3
                found = true; break
            end
        end
        if found
            partial += 1
        elseif vnorm(pb - pa) < 0.25
            tiny += 1
        else
            push!(gaps, (pa, pb))
        end
    end
    push!(res, ("strip boundary edges shared with a clipped face edge", isempty(gaps),
                "$(length(open_edges)) open strip edges: $exact exact, $partial collinear-partial (T-junction), $tiny tiny (<0.25u) unmatched, $(length(gaps)) longer unmatched; $n_cap_open wall-end edges on/in a wall face excluded"))
    res, gaps
end
