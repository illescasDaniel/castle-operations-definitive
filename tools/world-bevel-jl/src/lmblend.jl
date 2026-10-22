# Continuous lighting across bevel strips (plan P2).
#
# Every strip / corner / cap vertex gets its own lightmap texel (grid blocks per strip half, 2x2 per corner/cap triangle) instead of
# clamping to the edge texel of its own face's rect: the two halves fade smoothly to the average of the two faces' edge light at the
# seam. Faces that own such blocks get their lightmap rect copied (with a 1 texel replicate gutter) plus the blocks into an
# appended 128x128 page; all their UVs are translated, so faces away from the corners stay pixel-identical.

const LM_BLOCK_ROWS = 96

@inline col_add(a::RGB3, b::RGB3) = (a[1] + b[1], a[2] + b[2], a[3] + b[3])
@inline col_lerp(a::RGB3, b::RGB3, s::Float64) = (a[1] + s * (b[1] - a[1]), a[2] + s * (b[2] - a[2]), a[3] + s * (b[3] - a[3]))
function col_mean(c::Vector{RGB3})::RGB3
    r = g = b = 0.0
    for x in c
        r += x[1]; g += x[2]; b += x[3]
    end
    n = length(c)
    (r / n, g / n, b / n)
end

"Lightmap colour of face f (own page, clamped like the old UVs) at 3D point x."
function lm_at(bv::Bevel, f::Face, x::V3)::RGB3
    m = eval_map(f, x - (vdot(x, f.n) - f.d) * f.n)
    lm_sample(bv.lm, Int(bv.S[f.si+1].lmn), m[3], m[4])
end

@inline fade_s(u::Float64) = (x = clamp(u, 0.0, 1.0); 0.5 * x + 0.5 * x * x * (3 - 2x))

const DIAG_EDGE = Float64[]
const DIAG_EDGE_WHO = Any[]

@inline rgb_lerp(a::Tuple, b::Tuple, s::Float64) = (a[1] + s * (b[1] - a[1]), a[2] + s * (b[2] - a[2]), a[3] + s * (b[3] - a[3]))
@inline v3lerp(a::V3, b::V3, s::Float64) = V3(a.x + s * (b.x - a.x), a.y + s * (b.y - a.y), a.z + s * (b.z - a.z))

"Light of both faces on the cut lines at xa (face A edge) and xb (face B edge); a face without lightmap takes the other's value."
function ab_light(bv::Bevel, fa::Face, fb::Face, xa::V3, xb::V3)::Tuple{RGB3,RGB3}
    LA = fa.has_lm ? lm_at(bv, fa, xa) : nothing
    LB = fb.has_lm ? lm_at(bv, fb, xb) : nothing
    LA === nothing && (LA = LB)
    LB === nothing && (LB = LA)
    LA, LB
end

"Colours of the columns `ks` for edge lights LA, LB: linear cross-fade over the strip (phi 0 = face A edge, 1 = face B edge)."
cols_from(LA::RGB3, LB::RGB3, phis::Vector{Float64}, ks) = RGB3[col_lerp(LA, LB, fade_s(phis[k])) for k in ks]

const SEAM_CLS_OF = Dict{Int,Symbol}()
const SEAM_OF = Dict{Int,SeamRec}()
const ROWS_OF = Dict{Int,Vector{Float64}}()

"""
Extend (or start) the block of one strip half over the interval between rows ra and rb: texel rows are spaced `lm_pitch` units apart
along the edge (uniform inside the interval, so the quad's texture coordinate is linear in t) and sample the real face light at the cut
lines. Returns (block, block id, row index at ra, row index at rb).
"""
function strip_block!(bv::Bevel, cur::Vector{Any}, h::Int, fa::Face, fb::Face, half::Int, ra::Row, rb::Row, phis, im::Int, np::Int, cls::Symbol, owner::Union{Nothing,Face}=nothing)
    f, fo = half == 0 ? (fa, fb) : (fb, fa)
    owner !== nothing && ((f, fo) = (owner, owner === fa ? fb : fa))
    ks = half == 0 ? (1:im) : (im:np)
    p = bv.a.lm_pitch
    nsub = p <= 0 ? 1 : clamp(ceil(Int, (rb.t - ra.t) / p - 1e-9), 1, 90)
    c = cur[h]
    function addrow!(b, u)
        xa = v3lerp(ra.pts[1], rb.pts[1], u); xb = v3lerp(ra.pts[np], rb.pts[np], u)
        LA, LB = ab_light(bv, fa, fb, xa, xb)
        append!(b.col, cols_from(LA, LB, phis, ks))
        b.nr += 1
    end
    if c === nothing || c[1].si != f.si || c[3] != fo.si || c[1].nr + nsub > LM_BLOCK_ROWS
        b = LmBlock(f.si, 0, length(ks), RGB3[], 0, 0, cls)
        push!(bv.blocks, b)
        c = (b, length(bv.blocks), fo.si)
        cur[h] = c
        addrow!(b, 0.0)
    end
    b = c[1]
    r0 = b.nr
    for j in 1:nsub
        addrow!(b, j / nsub)
    end
    c[1], c[2], r0, b.nr
end

"Deviation between the light the chart represents (linear between its rows) and the light the faces show at the cut lines."
function diag_rows!(bv::Bevel, fa::Face, fb::Face, ra::Row, rb::Row, np::Int)::Float64
    (fa.has_lm || fb.has_lm) || return 0.0
    p = bv.a.lm_pitch
    nsub = p <= 0 ? 1 : clamp(ceil(Int, (rb.t - ra.t) / p - 1e-9), 1, 90)
    xa(u) = v3lerp(ra.pts[1], rb.pts[1], u)
    xb(u) = v3lerp(ra.pts[np], rb.pts[np], u)
    rowsA = RGB3[]; rowsB = RGB3[]
    for j in 0:nsub
        LA, LB = ab_light(bv, fa, fb, xa(j / nsub), xb(j / nsub))
        push!(rowsA, LA); push!(rowsB, LB)
    end
    worst = 0.0
    nchk = max(3, min(24, ceil(Int, (rb.t - ra.t) / 2)))
    for k in 1:nchk-1
        u = k / nchk
        j = min(floor(Int, u * nsub), nsub - 1)
        fr = u * nsub - j
        LA, LB = ab_light(bv, fa, fb, xa(u), xb(u))
        for (tru, rows) in ((LA, rowsA), (LB, rowsB))
            rep = rgb_lerp(rows[j+1], rows[j+2], fr)
            y1, y2 = lum(tru), lum(rep)
            e = abs(y1 - y2) / max(y1, y2, 4.0)
            push!(DIAG_EDGE, e)
            worst = max(worst, e)
        end
    end
    worst
end

"2x2 block for one triangle with vertex colours c: vertices at texels (1,1), (1,2), (2,1); the 4th texel extends the plane so the interpolation stays linear."
function tri_block!(bv::Bevel, f::Face, c::NTuple{3,Any})
    c0, c1, c2 = c[1]::RGB3, c[2]::RGB3, c[3]::RGB3
    c3 = (c1[1] + c2[1] - c0[1], c1[2] + c2[2] - c0[2], c1[3] + c2[3] - c0[3])
    push!(bv.blocks, LmBlock(f.si, 2, 2, RGB3[c0, c1, c2, c3], 0, 0, :none))
    (length(bv.blocks), (1f0, 1f0, 1f0, 2f0, 2f0, 1f0))
end

function push_strip!(f::Face, T::Tri, kind::UInt8, gid::Int, bid::Int, p6::NTuple{6,Float32})
    push!(f.strip, T); push!(f.skind, kind); push!(f.sgid, Int32(gid)); push!(f.sblk, Int32(bid)); push!(f.spos, p6)
    nothing
end

# --- packing ---------------------------------------------------------------------------------------------------------------

mutable struct LmUnit
    si::Int
    items::Vector{NTuple{4,Int}}     # (x, y, w, h) inside the unit; item 0 = rect copy, then the blocks (ids in `bids`)
    bids::Vector{Int}
    bw::Int; bh::Int
    page::Int; px::Int; py::Int      # placement (page counted from 0 among the new pages)
end

"Shelf-pack a face's rect copy + blocks into one unit of at most 128x128; nothing when they do not fit."
function make_unit(bv::Bevel, f::Face, bids::Vector{Int})::Union{Nothing,LmUnit}
    s = bv.S[f.si+1]
    rw, rh = Int(s.lmw) + 2, Int(s.lmh) + 2
    (rw <= LM_SIZE && rh <= LM_SIZE) || return nothing
    sizes = NTuple{3,Int}[(0, rw, rh)]   # (id, w, h)
    for b in bids
        bl = bv.blocks[b]
        push!(sizes, (b, bl.nc + 2, bl.nr + 2))
    end
    total = sum(x[2] * x[3] for x in sizes)
    order = sortperm(sizes, by=x -> (-x[3], -x[2]))
    W = clamp(ceil(Int, sqrt(total) * 1.3), maximum(x[2] for x in sizes), LM_SIZE)
    items = NTuple{4,Int}[]; ids = Int[]
    x = 0; y = 0; rowh = 0; bw = 0
    for oi in order
        id, w, h = sizes[oi]
        if x + w > W
            y += rowh; x = 0; rowh = 0
        end
        y + h <= LM_SIZE || return nothing
        push!(items, (x, y, w, h)); push!(ids, id)
        x += w; rowh = max(rowh, h); bw = max(bw, x)
    end
    LmUnit(f.si, items, ids, bw, y + rowh, -1, 0, 0)
end

"Pack units into pages (first fit shelves). Returns the number of pages."
function pack_units!(units::Vector{LmUnit})
    shelves = Vector{Vector{NTuple{3,Int}}}()   # per page: (y, h, xused)
    pageh = Int[]
    sort!(units, by=u -> (-u.bh, -u.bw))
    for u in units
        placed = false
        for (pi, sh) in enumerate(shelves)
            for (k, (y, h, xu)) in enumerate(sh)
                if u.bh <= h && xu + u.bw <= LM_SIZE
                    u.page, u.px, u.py = pi - 1, xu, y
                    sh[k] = (y, h, xu + u.bw)
                    placed = true; break
                end
            end
            placed && break
            if pageh[pi] + u.bh <= LM_SIZE
                push!(sh, (pageh[pi], u.bh, u.bw))
                u.page, u.px, u.py = pi - 1, 0, pageh[pi]
                pageh[pi] += u.bh
                placed = true; break
            end
        end
        if !placed
            push!(shelves, [(0, u.bh, u.bw)])
            push!(pageh, u.bh)
            u.page, u.px, u.py = length(shelves) - 1, 0, 0
        end
    end
    length(shelves)
end

"Plan the relocation: units for every face that owns blocks. Returns (placed units by surface, number of new pages)."
function plan_lightmaps!(bv::Bevel)
    byface = Dict{Int,Vector{Int}}()
    for (i, b) in enumerate(bv.blocks)
        push!(get!(byface, b.si, Int[]), i)
    end
    units = LmUnit[]
    for (si, bids) in sort!(collect(byface), by=first)
        f = face(bv, si)
        u = f.has_lm && bv.S[si+1].lmw > 0 && bv.S[si+1].lmh > 0 ? make_unit(bv, f, bids) : nothing
        if u === nothing
            inc!(bv, "lm_fallback_faces")
        else
            push!(units, u)
        end
    end
    npages = pack_units!(units)
    Dict{Int,LmUnit}(u.si => u for u in units), npages
end

"Build the extended lightmap lump. `plan`: surface -> unit. Returns (lump bytes, first new page index, page stride)."
function build_lightmaps(bv::Bevel, plan::Dict{Int,LmUnit}, npages::Int)
    lm0 = bv.lm
    n0 = length(lm0) ÷ LM_PAGE_BYTES
    deluxe = n0 > 1 && !any(s -> s.lmn >= 0 && (s.lmn & 1) != 0, bv.S)
    stride = deluxe ? 2 : 1
    base = n0 + (isodd(n0) && deluxe ? 1 : 0)
    pad = (base - n0) * LM_PAGE_BYTES
    out = zeros(UInt8, (base + stride * npages) * LM_PAGE_BYTES)
    copyto!(out, 1, lm0, 1, length(lm0))
    if deluxe  # flat normal-map filler for the deluxe companion of every new page
        for j in 0:npages-1
            o = (base + stride * j + 1) * LM_PAGE_BYTES
            for p in 0:LM_SIZE*LM_SIZE-1
                out[o+3p+1] = 128; out[o+3p+2] = 128; out[o+3p+3] = 255
            end
        end
    end
    for (si, u) in plan
        s = bv.S[si+1]
        page = base + stride * u.page
        src = Int(s.lmn) * LM_PAGE_BYTES
        pg = page * LM_PAGE_BYTES
        putpx!(x, y, r, g, b) = (o = pg + (y * LM_SIZE + x) * 3; out[o+1] = r; out[o+2] = g; out[o+3] = b)
        # rect copy with replicate gutter (item 0)
        k0 = findfirst(==(0), u.bids)
        (ix, iy, iw, ih) = u.items[k0]
        for yy in 0:ih-1, xx in 0:iw-1
            sx = clamp(Int(s.lmx) + xx - 1, Int(s.lmx), Int(s.lmx) + Int(s.lmw) - 1)
            sy = clamp(Int(s.lmy) + yy - 1, Int(s.lmy), Int(s.lmy) + Int(s.lmh) - 1)
            o = src + (sy * LM_SIZE + sx) * 3
            putpx!(u.px + ix + xx, u.py + iy + yy, lm0[o+1], lm0[o+2], lm0[o+3])
        end
        for (k, id) in enumerate(u.bids)
            id == 0 && continue
            b = bv.blocks[id]
            (bx, by, _w, _h) = u.items[k]
            b.bx = u.px + bx + 1; b.by = u.py + by + 1   # 1 texel replicate ring around the block (no bleed from zero texels)
            for r in 0:b.nr+1, c in 0:b.nc+1
                col = b.col[(clamp(r, 1, b.nr) - 1) * b.nc + clamp(c, 1, b.nc)]
                bv.a.debug_lm == "class" && (col = class_rgb(b.cls))
                putpx!(b.bx + c - 1, b.by + r - 1, UInt8(clamp(round(col[1]), 0, 255)), UInt8(clamp(round(col[2]), 0, 255)), UInt8(clamp(round(col[3]), 0, 255)))
            end
        end
        inc!(bv, "lm_faces_blocks")
        inc!(bv, "lm_rect_texels", iw * ih)
    end
    inc!(bv, "lm_block_texels", sum(b.nr * b.nc for b in bv.blocks))
    bv.stats["lm_pages_added"] = npages
    out, base, stride
end
