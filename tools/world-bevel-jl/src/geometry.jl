# Small float64 vector type and the polygon clipping helpers (ports of unit/poly_area2/mk_poly/split_plane/...).

struct V3
    x::Float64
    y::Float64
    z::Float64
end
@inline Base.:+(a::V3, b::V3) = V3(a.x + b.x, a.y + b.y, a.z + b.z)
@inline Base.:-(a::V3, b::V3) = V3(a.x - b.x, a.y - b.y, a.z - b.z)
@inline Base.:-(a::V3) = V3(-a.x, -a.y, -a.z)
@inline Base.:*(a::V3, s::Real) = V3(a.x * s, a.y * s, a.z * s)
@inline Base.:*(s::Real, a::V3) = V3(s * a.x, s * a.y, s * a.z)
@inline Base.:/(a::V3, s::Real) = V3(a.x / s, a.y / s, a.z / s)
@inline vdot(a::V3, b::V3) = a.x * b.x + a.y * b.y + a.z * b.z
@inline vcross(a::V3, b::V3) = V3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)
@inline vnorm(a::V3) = sqrt(vdot(a, a))
@inline unit(v::V3) = (n = vnorm(v); n > 0 ? v / n : v)
@inline vmaxabs(a::V3) = max(abs(a.x), abs(a.y), abs(a.z))
const ZERO3 = V3(0.0, 0.0, 0.0)

# vertex attribute row: xyz(3) st(2) lm(2) n(3) color(4), float64
const NATT = 14
const Att = NTuple{14,Float64}
const Poly = Vector{Att}
@inline axyz(a::Att) = V3(a[1], a[2], a[3])
@inline anrm(a::Att) = V3(a[8], a[9], a[10])
@inline mkatt(p::V3, m::NTuple{4,Float64}, n::V3, c::NTuple{4,Float64}) =
    (p.x, p.y, p.z, m[1], m[2], m[3], m[4], n.x, n.y, n.z, c[1], c[2], c[3], c[4])
@inline acolor(a::Att) = (a[11], a[12], a[13], a[14])
@inline att_lerp(a::Att, b::Att, s::Float64) = ntuple(i -> a[i] + s * (b[i] - a[i]), Val(14))

const EPS = 1e-9

# 3x3 solve with partial pivoting; nothing when singular
function solve3(M::NTuple{3,V3}, rhs::NTuple{3,Float64})
    a = [M[1].x M[1].y M[1].z rhs[1]; M[2].x M[2].y M[2].z rhs[2]; M[3].x M[3].y M[3].z rhs[3]]
    for c in 1:3
        p = c
        for r in c+1:3
            abs(a[r, c]) > abs(a[p, c]) && (p = r)
        end
        a[p, c] == 0.0 && return nothing
        if p != c
            for k in 1:4
                a[c, k], a[p, k] = a[p, k], a[c, k]
            end
        end
        for r in c+1:3
            f = a[r, c] / a[c, c]
            for k in c:4
                a[r, k] -= f * a[c, k]
            end
        end
    end
    x3 = a[3, 4] / a[3, 3]
    x2 = (a[2, 4] - a[2, 3] * x3) / a[2, 2]
    x1 = (a[1, 4] - a[1, 2] * x2 - a[1, 3] * x3) / a[1, 1]
    V3(x1, x2, x3)
end

@inline tri_area2(a::V3, b::V3, c::V3) = vnorm(vcross(b - a, c - a))

function poly_area2(P::Poly)
    x0 = axyz(P[1])
    s = ZERO3
    for i in 2:length(P)-1
        s = s + vcross(axyz(P[i]) - x0, axyz(P[i+1]) - x0)
    end
    length(P) >= 3 ? vnorm(s) : 0.0
end

function mk_poly(pts::Vector{Att})
    out = Att[]
    for p in pts
        if !isempty(out) && vmaxabs(axyz(out[end]) - axyz(p)) < 1e-7
            continue
        end
        push!(out, p)
    end
    if length(out) > 1 && vmaxabs(axyz(out[1]) - axyz(out[end])) < 1e-7
        pop!(out)
    end
    length(out) < 3 && return nothing
    poly_area2(out) > 1e-7 ? out : nothing
end

# python tuple comparison a[:3] > b[:3] (== treats -0.0 and 0.0 as equal)
@inline function xyz_gt(a::Att, b::Att)
    a[1] != b[1] && return a[1] > b[1]
    a[2] != b[2] && return a[2] > b[2]
    return a[3] > b[3]
end

@inline function interp_att(a::Att, b::Att, da::Float64, db::Float64)
    if xyz_gt(a, b)
        a, b, da, db = b, a, db, da
    end
    s = da / (da - db)
    att_lerp(a, b, s)
end

const PolyOrNothing = Union{Poly,Nothing}

"Split by signed distances. Returns (positive part, negative part); either may be nothing."
function split_plane(P::Poly, sd0::Vector{Float64})::Tuple{PolyOrNothing,PolyOrNothing}
    k = length(P)
    sd = Vector{Float64}(undef, k)
    mn = Inf
    mx = -Inf
    for i in 1:k
        v = abs(sd0[i]) < EPS ? 0.0 : sd0[i]
        sd[i] = v
        mn = min(mn, v)
        mx = max(mx, v)
    end
    mn >= 0 && return (P, nothing)
    mx <= 0 && return (nothing, P)
    pos = Att[]
    neg = Att[]
    for i in 1:k
        j = i == k ? 1 : i + 1
        da, db = sd[i], sd[j]
        da >= 0 && push!(pos, P[i])
        da <= 0 && push!(neg, P[i])
        if da * db < 0
            x = interp_att(P[i], P[j], da, db)
            push!(pos, x)
            push!(neg, x)
        end
    end
    (mk_poly(pos), mk_poly(neg))
end

const Tri = NTuple{3,Att}

function triangulate(P::Poly)::Vector{Tri}
    k = length(P)
    k == 3 && return [(P[1], P[2], P[3])]
    for a in 0:k-1
        tris = Tri[]
        for i in 1:k-2
            t = (P[a+1], P[(a+i)%k+1], P[(a+i+1)%k+1])
            tri_area2(axyz(t[1]), axyz(t[2]), axyz(t[3])) > 1e-7 && push!(tris, t)
        end
        if length(tris) == k - 2 || (a == k - 1 && !isempty(tris))
            return tris
        end
    end
    Tri[(P[1], P[i+1], P[i+2]) for i in 1:k-2 if tri_area2(axyz(P[1]), axyz(P[i+1]), axyz(P[i+2])) > 1e-7]
end

@inline quant_key(q::Att) = (round(Int64, q[1] * 1e4), round(Int64, q[2] * 1e4), round(Int64, q[3] * 1e4))

"Hertel-Mehlhorn style merge of the pieces of a clipped face (port of merge_convex)."
function merge_convex(polys::Vector{Poly}, nrm::V3)::Vector{Poly}
    items = Union{Nothing,Tuple{Vector{NTuple{3,Int64}},Poly}}[]
    dropped_polys = Poly[]
    for P in polys
        ks = [quant_key(q) for q in P]
        if length(unique(ks)) == length(ks)
            push!(items, (ks, P))
        else
            push!(dropped_polys, P)
        end
    end
    changed = true
    while changed
        changed = false
        edge = Dict{Tuple{NTuple{3,Int64},NTuple{3,Int64}},Tuple{Int,Int}}()
        for (i, it) in enumerate(items)
            ks = it[1]
            for k in 1:length(ks)
                edge[(ks[k], ks[k%length(ks)+1])] = (i, k)
            end
        end
        for i in 1:length(items)
            ks, P = items[i]
            ki = length(ks)
            for k in 1:ki
                a_, b_ = ks[k], ks[k%ki+1]
                hit = get(edge, (b_, a_), nothing)
                (hit === nothing || hit[1] == i || items[hit[1]] === nothing) && continue
                j, kj = hit
                kj_, Pj = items[j]
                # [b ... a] of i, then j after the shared edge up to before b   (k, kj are 1-based here)
                rot_i = [(k + m) % ki + 1 for m in 0:ki-1]                # python (k0+1+m) % ki with k0 = k-1
                nj = length(kj_)
                rot_j = [(kj + 1 + m) % nj + 1 for m in 0:nj-3]           # python (kj0+2+m) % nj
                nk = vcat(ks[rot_i], kj_[rot_j])
                length(unique(nk)) != length(nk) && continue
                nP = vcat(P[rot_i], Pj[rot_j])
                n = length(nP)
                bad = false
                for q in 1:n
                    x0 = axyz(nP[q]); x1 = axyz(nP[q%n+1]); x2 = axyz(nP[(q+1)%n+1])
                    e1 = x1 - x0
                    e2 = x2 - x1
                    cr = vdot(vcross(e1, e2), nrm)
                    if cr < -1e-6 * max(vnorm(e1) * vnorm(e2), 1e-9)
                        bad = true
                        break
                    end
                end
                bad && continue
                items[i] = (nk, nP)
                items[j] = nothing
                changed = true
                break
            end
            changed && break
        end
        changed && filter!(!isnothing, items)
    end
    out = Poly[it[2] for it in items]
    append!(out, dropped_polys)
    out
end

function slerp(a::V3, b::V3, f::Float64, theta::Float64)
    (sin((1 - f) * theta) * a + sin(f * theta) * b) / sin(theta)
end
