# Diagnostics: lightmap sampling helpers, --dump-near, and per-run lightmap statistics (P0).

const LM_SIZE = 128
const LM_PAGE_BYTES = LM_SIZE * LM_SIZE * 3

"Bilinear sample (GL_LINEAR, clamp to edge) of lightmap page `page` (0-based) at page UV (u, v) in 0..1. Returns 0..255 floats."
function lm_sample(lm::Vector{UInt8}, page::Int, u::Float64, v::Float64)::NTuple{3,Float64}
    x = u * LM_SIZE - 0.5
    y = v * LM_SIZE - 0.5
    x0 = floor(Int, x); y0 = floor(Int, y)
    fx = x - x0; fy = y - y0
    base = page * LM_PAGE_BYTES
    r = 0.0; g = 0.0; b = 0.0
    for (dy, wy) in ((0, 1 - fy), (1, fy)), (dx, wx) in ((0, 1 - fx), (1, fx))
        xx = clamp(x0 + dx, 0, LM_SIZE - 1)
        yy = clamp(y0 + dy, 0, LM_SIZE - 1)
        o = base + (yy * LM_SIZE + xx) * 3
        w = wx * wy
        r += w * lm[o+1]; g += w * lm[o+2]; b += w * lm[o+3]
    end
    (r, g, b)
end

@inline lum(c::NTuple{3,Float64}) = 0.299 * c[1] + 0.587 * c[2] + 0.114 * c[3]

const DIAG_STEPS = Float64[]

"Record the seam luminance step between the two half faces at one strip row (original lightmap, no fade)."
function diag_step!(bv::Bevel, fa::Face, fb::Face, xa::V3, xb::V3)
    inc!(bv, "diag_halves_rows")
    (fa.has_lm && fb.has_lm) || return
    sa, sb = bv.S[fa.si+1], bv.S[fb.si+1]
    sa.lmn != sb.lmn && inc!(bv, "diag_halves_diff_page")
    ma, mb = eval_map(fa, xa), eval_map(fb, xb)
    ca = lm_sample(bv.lm, Int(sa.lmn), ma[3], ma[4])
    cb = lm_sample(bv.lm, Int(sb.lmn), mb[3], mb[4])
    ya, yb = lum(ca), lum(cb)
    push!(DIAG_STEPS, abs(ya - yb) / max(ya, yb, 4.0))
    nothing
end

"Triangle (strip / corner / cap) dump for all triangles with a vertex within R of p."
function dump_near(bv::Bevel, p::V3, R::Float64)
    kinds = ("strip", "corner", "cap")
    n = 0
    for f in bv.flist
        isempty(f.strip) && continue
        s = bv.S[f.si+1]
        for (k, T) in enumerate(f.strip)
            any(q -> vnorm(axyz(q) - p) <= R, T) || continue
            n += 1
            lm_ok = all(q -> isfinite(q[6]) && isfinite(q[7]), T)
            @printf("tri %d: %s gid=%d face=%d shader=%s lmn=%d rect=(%d,%d %dx%d) has_lm=%s planar_err=%.3f fit_err_lm=%.2e finite=%s\n",
                    n, kinds[f.skind[k]], f.sgid[k], f.si, f.name, s.lmn, s.lmx, s.lmy, s.lmw, s.lmh, f.has_lm, f.planar_err, f.fit_err_lm, lm_ok)
            for q in T
                clamped = f.has_lm && (abs(q[6] - f.lm_lo[1]) < 1e-6 || abs(q[6] - f.lm_hi[1]) < 1e-6 || abs(q[7] - f.lm_lo[2]) < 1e-6 || abs(q[7] - f.lm_hi[2]) < 1e-6)
                @printf("    xyz (%.2f %.2f %.2f) st (%.4f %.4f) lm_px (%.3f %.3f) clamped=%s col (%d %d %d %d)\n",
                        q[1], q[2], q[3], q[4], q[5], q[6] * 128, q[7] * 128, clamped, q[11], q[12], q[13], q[14])
            end
        end
    end
    println("dump-near: $n triangles within $R of ($(p.x), $(p.y), $(p.z))")
end

"Lightmap related statistics after run!: non-finite lm, strips/caps without lightmap, halves on different pages."
function lm_diag!(bv::Bevel)
    nonfinite = 0; badgeo = 0; nolm = 0; nolm_cap = 0; ntri = 0
    for f in bv.flist
        isempty(f.strip) && continue
        for (k, T) in enumerate(f.strip)
            ntri += 1
            all(q -> isfinite(q[6]) && isfinite(q[7]), T) || (nonfinite += 1)
            if !all(q -> all(i -> isfinite(q[i]), 1:5) && abs(q[4]) < 1e4 && abs(q[5]) < 1e4, T)
                badgeo += 1
                badgeo <= 20 && @printf("  bad geometry/st tri: shader=%s face=%d kind=%d xyz (%.1f %.1f %.1f) st (%g %g)\n", f.name, f.si, f.skind[k], T[1][1], T[1][2], T[1][3], T[1][4], T[1][5])
            end
            if !f.has_lm
                nolm += 1
                f.skind[k] == 0x03 && (nolm_cap += 1)
            end
        end
    end
    if !isempty(DIAG_STEPS)
        sort!(DIAG_STEPS)
        n = length(DIAG_STEPS)
        bv.stats["diag_step_median"] = DIAG_STEPS[(n + 1) ÷ 2]
        bv.stats["diag_step_p95"] = DIAG_STEPS[max(1, ceil(Int, 0.95 * n))]
        bv.stats["diag_step_max"] = DIAG_STEPS[end]
    end
    if !isempty(DIAG_EDGE)
        sort!(DIAG_EDGE)
        n = length(DIAG_EDGE)
        bv.stats["diag_edge_median"] = DIAG_EDGE[(n + 1) ÷ 2]
        bv.stats["diag_edge_p90"] = DIAG_EDGE[max(1, ceil(Int, 0.90 * n))]
        bv.stats["diag_edge_p95"] = DIAG_EDGE[max(1, ceil(Int, 0.95 * n))]
        bv.stats["diag_edge_max"] = DIAG_EDGE[end]
        for w in DIAG_EDGE_WHO
            println("  edge mismatch: ", w)
        end
    end
    bv.stats["diag_strip_tris"] = ntri
    bv.stats["diag_nonfinite_lm_tris"] = nonfinite
    bv.stats["diag_nolm_tris"] = nolm
    bv.stats["diag_nolm_cap_tris"] = nolm_cap
    nothing
end

function print_lm_diag(bv::Bevel)
    st(k) = (v = stat(bv, k); v == round(v) ? string(Int(v)) : @sprintf("%.3f", v))
    println("lightmap diag: strip/cap/corner tris ", st("diag_strip_tris"), "; non-finite lm tris ", st("diag_nonfinite_lm_tris"),
            "; tris on faces without lightmap ", st("diag_nolm_tris"), " (caps ", st("diag_nolm_cap_tris"), ")")
    println("  halves on different lightmap pages (strip rows): ", st("diag_halves_diff_page"), " of ", st("diag_halves_rows"),
            "; luminance step at the seam |dY|/Y: median ", st("diag_step_median"), ", p95 ", st("diag_step_p95"), ", max ", st("diag_step_max"))
    if stat(bv, "lm_faces_blocks") > 0 || stat(bv, "lm_fallback_faces") > 0
        println("  continuous lighting: faces with blocks ", st("lm_faces_blocks"), " (rect copies ", st("lm_rect_texels"), " texels, block texels ", st("lm_block_texels"),
                "), appended pages ", st("lm_pages_added"), ", fallback faces (did not fit) ", st("lm_fallback_faces"), " (", round(100 * stat(bv, "lm_fallback_faces") / max(1.0, stat(bv, "lm_fallback_faces") + stat(bv, "lm_faces_blocks")), digits=2), "%)", ", extra rows ", st("lm_rows_added"),
                "; chart-vs-face light deviation |dY|/Y median ", st("diag_edge_median"), " p90 ", st("diag_edge_p90"), " p95 ", st("diag_edge_p95"), " max ", st("diag_edge_max"))
    end
end

# --- P5: seam report, class table, probe-spot, debug shader / lightmap colours -------------------------------------------------

const CLASS_ORDER = (:compat, :mirror, :along, :scale, :rot, :diff)
const CLASS_NAME = Dict(:compat => "compatible", :mirror => "mirrored across the corner", :along => "reversed along the edge",
                        :scale => "scale ratio > 1.15", :rot => "rotated axes", :diff => "different shaders")

function print_class_table(bv::Bevel)
    isempty(bv.seams) && return
    t0 = class_table(bv, :cls0); t1 = class_table(bv, :cls)
    tot0 = max(sum(values(t0)), 1e-9); tot1 = max(sum(values(t1)), 1e-9)
    nb = count(r -> r.gid > 0, bv.seams)
    @printf("texture classes by seam length (%d bevelled runs + %d concave seams, %.0f units); before flips -> after flips\n", nb, length(bv.seams) - nb, tot0)
    for c in CLASS_ORDER
        @printf("  %-28s %6.1f%% -> %6.1f%%\n", CLASS_NAME[c], 100 * get(t0, c, 0.0) / tot0, 100 * get(t1, c, 0.0) / tot1)
    end
    nflip = stat(bv, "flip_components")
    @printf("  flipped components: %d (%d faces)\n", nflip, stat(bv, "flip_faces"))
    # same-shader seams only: leftover offset
    rs = Float64[]; ws = Float64[]
    for r in bv.seams
        (isnan(r.resid) || r.cls == :diff) && continue
        push!(rs, r.resid); push!(ws, r.len)
    end
    if !isempty(rs)
        good = sum(w for (x, w) in zip(rs, ws) if x < 0.05)
        @printf("  same-shader seams with leftover offset < 0.05 period: %.1f%% of their length\n", 100 * good / sum(ws))
    end
end

function write_seam_report(bv::Bevel, path::AbstractString)
    open(path, "w") do io
        println(io, "gid\tkind\tlen\tsurfA\tsurfB\tshaderA\tshaderB\tclass_before\tclass_after\tflipA\tflipB\tleftover_offset\tband_stretch\tlight_dev\taA\tcA\taB\tcB")
        f2(v) = @sprintf("%.4f,%.4f", v[1], v[2])
        for r in bv.seams
            @printf(io, "%d\t%s\t%.1f\t%d\t%d\t%s\t%s\t%s\t%s\t%d%d\t%d%d\t%.3f\t%.3f\t%.3f\t%s\t%s\t%s\t%s\n", r.gid, r.gid > 0 ? "bevel" : "concave", r.len, r.fa, r.fb,
                    r.shA, r.shB, r.cls0, r.cls, r.flipA[1], r.flipA[2], r.flipB[1], r.flipB[2], r.resid, r.stretch, r.lmdev, f2(r.der1[1:2]), f2(r.der1[3:4]), f2(r.der1[5:6]), f2(r.der1[7:8]))
        end
    end
    println("wrote seam report $path ($(length(bv.seams)) seams)")
end

"Triangle (Moeller-Trumbore) hit distance or Inf; the ray direction is unit."
function ray_tri(o::V3, dir::V3, a::V3, b::V3, c::V3)::Float64
    e1 = b - a; e2 = c - a
    p = vcross(dir, e2)
    det = vdot(e1, p)
    abs(det) < 1e-12 && return Inf
    inv = 1 / det
    tv = o - a
    u = vdot(tv, p) * inv
    (u < 0 || u > 1) && return Inf
    q = vcross(tv, e1)
    v = vdot(dir, q) * inv
    (v < 0 || u + v > 1) && return Inf
    t = vdot(e2, q) * inv
    t > 0 ? t : Inf
end

function cam_dir(yaw::Float64, pitch::Float64)
    y, p = deg2rad(yaw), deg2rad(pitch)
    V3(cos(p) * cos(y), cos(p) * sin(y), -sin(p))
end

"Sample a chart block at fractional (row, col) like the GPU does (bilinear, clamp)."
function block_sample(b::LmBlock, r::Float64, c::Float64)::RGB3
    r = clamp(r, 1.0, Float64(b.nr)); c = clamp(c, 1.0, Float64(b.nc))
    r0 = min(floor(Int, r), max(b.nr - 1, 1)); c0 = min(floor(Int, c), max(b.nc - 1, 1))
    fr = r - r0; fc = c - c0
    g(rr, cc) = b.col[(min(rr, b.nr) - 1) * b.nc + min(cc, b.nc)]
    top = col_lerp(g(r0, c0), g(r0, c0 + 1), fc)
    bot = col_lerp(g(r0 + 1, c0), g(r0 + 1, c0 + 1), fc)
    col_lerp(top, bot, fr)
end

fmt3(c::RGB3) = @sprintf("(%.0f %.0f %.0f) Y=%.1f", c[1], c[2], c[3], lum(c))

"--probe-spot: cast rays from the camera into the tool's own geometry (face polygons and strips) and describe what is hit."
function probe_spot(bv::Bevel, spec::NTuple{5,Float64}, fan::Float64)
    o = V3(spec[1], spec[2], spec[3])
    yaw, pitch = spec[4], spec[5]
    @printf("probe-spot: camera (%.1f %.1f %.1f) yaw %.1f pitch %.1f fan %.1f deg\n", o.x, o.y, o.z, yaw, pitch, fan)
    rays = Tuple{Float64,Float64}[(0.0, 0.0)]
    if fan > 0
        for dy in (-fan, -fan / 2, 0.0, fan / 2, fan), dp in (-fan / 2, 0.0, fan / 2)
            (dy == 0 && dp == 0) || push!(rays, (dy, dp))
        end
    end
    seen = Set{Tuple{Int,Int,Int}}()
    for (ri, (dy, dp)) in enumerate(rays)
        dir = cam_dir(yaw + dy, pitch + dp)
        best = Inf; bk = nothing
        for f in bv.flist
            f.polys === nothing && continue
            isempty(f.strip) && continue
            # strips and caps
            for (k, T) in enumerate(f.strip)
                t = ray_tri(o, dir, axyz(T[1]), axyz(T[2]), axyz(T[3]))
                if t < best
                    best = t; bk = (:strip, f, k)
                end
            end
            for P in f.polys
                length(P) < 3 && continue
                for i in 2:length(P)-1
                    t = ray_tri(o, dir, axyz(P[1]), axyz(P[i]), axyz(P[i+1]))
                    if t < best
                        best = t; bk = (:face, f, 0)
                    end
                end
            end
        end
        bk === nothing && (ri == 1 && println("  centre ray: no hit in modified geometry"); continue)
        kind, f, k = bk
        key = (kind == :strip ? Int(f.sgid[k]) : -1, f.si, kind == :strip ? Int(f.skind[k]) : 0)
        (ri > 1 && key in seen) && continue
        push!(seen, key)
        x = o + dir * best
        @printf("  ray %d (dyaw %.1f dpitch %.1f): %s hit at dist %.1f (%.1f %.1f %.1f) surf %d shader %s lmn %d\n", ri, dy, dp,
                kind == :strip ? ("strip", "corner patch", "wall cap")[Int(f.skind[k])] : "face polygon", best, x.x, x.y, x.z, f.si, f.name, bv.S[f.si+1].lmn)
        if kind == :face
            m = eval_map(f, x - (vdot(x, f.n) - f.d) * f.n)
            @printf("      st (%.4f %.4f); face light %s\n", m[1], m[2], fmt3(lm_at(bv, f, x)))
            continue
        end
        gid = Int(f.sgid[k])
        T = f.strip[k]
        @printf("      group %d surf %d block %d\n", gid, f.si, f.sblk[k])
        if gid > 0
            gr = bv.groups[gid]
            t = vdot(x - gr.P0, gr.d)
            rows = get(ROWS_OF, gid, Float64[])
            lo = findlast(<=(t), rows); hi = findfirst(>(t), rows)
            @printf("      t = %.2f in [%.2f, %.2f]; geometry rows %s; run lo/hi %.1f/%.1f, r=%.2f\n", t, lo === nothing ? NaN : rows[lo], hi === nothing ? NaN : rows[hi],
                    string(round.(rows, digits=1)), gr.lo, gr.hi, gr.r)
            fa, fb = face(bv, gr.fA.keys[1]), face(bv, gr.fB.keys[1])
            rec = get(SEAM_OF, gid, nothing)
            if rec !== nothing
                @printf("      shaders A %s | B %s; class %s (before flips %s); flips A %s B %s; leftover offset %.3f\n", rec.shA, rec.shB, rec.cls, rec.cls0, string(rec.flipA), string(rec.flipB), rec.resid)
                d = rec.der1; e = rec.der0
                @printf("      st derivatives after flips: A along (%.4f %.4f) across (%.4f %.4f) | B along (%.4f %.4f) across (%.4f %.4f); before flips A across (%.4f %.4f) B across (%.4f %.4f)\n",
                        d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8], e[3], e[4], e[7], e[8])
            end
            xa = gr.P0 + gr.d * t + gr.wA * gr.r; xb = gr.P0 + gr.d * t + gr.wB * gr.r
            LA = fa.has_lm ? lm_at(bv, fa, xa) : (0.0, 0.0, 0.0)
            LB = fb.has_lm ? lm_at(bv, fb, xb) : (0.0, 0.0, 0.0)
            @printf("      face light at the strip edge: A %s | B %s\n", fmt3(LA), fmt3(LB))
        end
        if f.sblk[k] > 0
            b = bv.blocks[f.sblk[k]]
            p = f.spos[k]
            # barycentric of the hit
            a_, b_, c_ = axyz(T[1]), axyz(T[2]), axyz(T[3])
            e1 = b_ - a_; e2 = c_ - a_; w = x - a_
            d11 = vdot(e1, e1); d12 = vdot(e1, e2); d22 = vdot(e2, e2); dw1 = vdot(w, e1); dw2 = vdot(w, e2)
            den = d11 * d22 - d12 * d12
            v = (d22 * dw1 - d12 * dw2) / den; u = (d11 * dw2 - d12 * dw1) / den
            ww = (1 - u - v, v, u)
            r = sum(ww[i] * p[2i-1] for i in 1:3); c = sum(ww[i] * p[2i] for i in 1:3)
            @printf("      block %dx%d (%s), texel (row %.2f col %.2f): block light %s\n", b.nr, b.nc, b.cls, r, c, fmt3(block_sample(b, Float64(r), Float64(c))))
        end
    end
end

# debug shader: asymmetric F-glyph grid, lightmap stage included
const UVGRID_SHADER = "textures/codmod_debug/uvgrid"
function uvgrid_tga()::Vector{UInt8}
    n = 256
    img = zeros(UInt8, n * n * 3)
    glyph = ["#######", "#######", "##.....", "##.....", "######.", "######.", "##.....", "##.....", "##.....", "##.....", "##.....", "##....."]
    for y in 0:n-1, x in 0:n-1
        gx, gy = x ÷ 32, y ÷ 32
        base = (gx + gy) % 2 == 0 ? (190, 190, 190) : (150, 150, 150)
        r, g, b = base
        # quadrant corner tints
        if x < 64 && y < 64; r, g, b = 235, 80, 80
        elseif x >= n - 64 && y < 64; r, g, b = 80, 220, 80
        elseif x < 64 && y >= n - 64; r, g, b = 90, 110, 240
        elseif x >= n - 64 && y >= n - 64; r, g, b = 240, 220, 70; end
        # big F in the middle: 7x12 cells of 12 px
        cx, cy = (x - 86) ÷ 12, (y - 56) ÷ 12
        if 0 <= cx < 7 && 0 <= cy < 12 && (x - 86) >= 0 && (y - 56) >= 0 && glyph[cy+1][cx+1] == '#'
            r, g, b = 20, 20, 20
        end
        (x % 32 == 0 || y % 32 == 0) && ((r, g, b) = (60, 60, 60))
        o = ((n - 1 - y) * n + x) * 3   # TGA is stored bottom-up: image row y (from the top) is written at n-1-y
        img[o+1] = UInt8(b); img[o+2] = UInt8(g); img[o+3] = UInt8(r)
    end
    hdr = UInt8[0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, n % 256, n ÷ 256, n % 256, n ÷ 256, 24, 0]
    vcat(hdr, img)
end

const UVGRID_SCRIPT = """
$(UVGRID_SHADER)
{
	{
		map \$lightmap
		rgbGen identity
	}
	{
		map textures/codmod_debug/uvgrid.tga
		blendFunc GL_DST_COLOR GL_ZERO
		rgbGen identity
	}
}
"""

const EXTRA_FILES = Pair{String,Vector{UInt8}}[]

function class_rgb(c::Symbol)::RGB3
    c == :compat ? (60.0, 200.0, 60.0) : c == :mirror ? (230.0, 50.0, 50.0) : c == :along ? (220.0, 60.0, 220.0) :
    c == :scale ? (230.0, 220.0, 50.0) : c == :rot ? (240.0, 140.0, 30.0) : c == :diff ? (60.0, 100.0, 240.0) : (120.0, 120.0, 120.0)
end
