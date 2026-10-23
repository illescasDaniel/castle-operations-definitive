# Command line driver: parse options, run bevel + smoothing, write the pk3.

function write_pk3(root, path, name, data::Vector{UInt8})
    chk = block_checksum(data)
    files = Pair{String,Vector{UInt8}}["maps/$name.bsp"=>data]
    append!(files, EXTRA_FILES)
    for (n, aas) in sort!(collect(find_aas(root, name)), by=first)
        push!(files, n => patch_aas(aas, chk))
        @printf("  %s: bspchecksum %#010x -> %#010x\n", n, aas_checksum(aas), chk)
    end
    mkpath(dirname(abspath(path)))
    zip_write(path, files)
    println("wrote $path ($(filesize(path)) bytes)")
end

function main(args::Vector{String}; root=nothing)
    root === nothing && (root = normpath(joinpath(@__DIR__, "..", "..", "..")))
    a = Opts()
    map = "escape1"; pk3 = nothing; smooth = nothing; nobevel = false; stats = false; dump = nothing
    probe = nothing; fan = 0.0; report = nothing; scan = false
    i = 1
    nxt() = (i += 1; i > length(args) && error("missing value for $(args[i-1])"); args[i])
    while i <= length(args)
        x = args[i]
        if startswith(x, "--") && occursin('=', x)
            k, v = split(x, '='; limit=2)
            args[i] = String(k); insert!(args, i + 1, String(v))
            x = args[i]
        end
        if x == "--map"; map = nxt()
        elseif x == "--pk3"; pk3 = nxt()
        elseif x == "--radius"; a.radius = parse(Float64, nxt())
        elseif x == "--segments"; a.segments = parse(Int, nxt())
        elseif x == "--taper"; a.taper = parse(Float64, nxt())
        elseif x == "--min-angle"; a.min_angle = parse(Float64, nxt())
        elseif x == "--max-angle"; a.max_angle = parse(Float64, nxt())
        elseif x == "--row-tol"; a.row_tol = parse(Float64, nxt())
        elseif x == "--min-length"; a.min_length = parse(Float64, nxt())
        elseif x == "--min-radius"; a.min_radius = parse(Float64, nxt())
        elseif x == "--skip-shader"; a.skip_shader = nxt()
        elseif x == "--surface-type"; a.surface_type = nxt()
        elseif x == "--uv-mode"; a.uv_mode = nxt()
        elseif x == "--align-stretch"; a.align_stretch = parse(Float64, nxt())
        elseif x == "--no-merge-polys"; a.merge_polys = false
        elseif x == "--wall-ends"; a.wall_ends = true
        elseif x == "--no-wall-ends"; a.wall_ends = false
        elseif x == "--mitre"; a.mitre = true
        elseif x == "--no-mitre"; a.mitre = false
        elseif x == "--lm-blend"; a.lm_blend = true
        elseif x == "--no-lm-blend"; a.lm_blend = false
        elseif x == "--wall-dot"; a.wall_dot = parse(Float64, nxt())
        elseif x == "--smooth-models"
            if i < length(args) && !startswith(args[i+1], "--")
                smooth = Regex(nxt())
            else
                smooth = DEFAULT_SMOOTH
            end
        elseif x == "--flip"; a.flip = true
        elseif x == "--no-flip"; a.flip = false
        elseif x == "--flip-skip"; a.flip_skip = nxt()
        elseif x == "--soft-width"; a.soft_width = parse(Float64, nxt())
        elseif x == "--wrap-prefer"; a.wrap_prefer = nxt()
        elseif x == "--lm-pitch"; a.lm_pitch = parse(Float64, nxt())
        elseif x == "--debug-shader"; a.debug_shader = nxt()
        elseif x == "--debug-lm"; a.debug_lm = nxt()
        elseif x == "--probe-spot"; probe = Tuple(parse.(Float64, split(replace(nxt(), "," => "."))))
        elseif x == "--probe-fan"; fan = parse(Float64, nxt())
        elseif x == "--seam-report"; report = nxt()
        elseif x == "--hole-scan"; scan = true
        elseif x == "--no-bevel"; nobevel = true
        elseif x == "--stats"; stats = true
        elseif x == "--dump-near"
            dump = (V3(parse(Float64, nxt()), parse(Float64, nxt()), parse(Float64, nxt())), parse(Float64, nxt()))
        else
            error("unknown option $x (supported: --map --pk3 --radius --segments --taper --min-angle --max-angle --row-tol --min-length --min-radius --skip-shader --surface-type --uv-mode --[no-]merge-polys --[no-]wall-ends --[no-]mitre --wall-dot --[no-]lm-blend --smooth-models [REGEX] --no-bevel --stats --dump-near X Y Z R --probe-spot \"x y z yaw pitch\" --probe-fan DEG --seam-report FILE --hole-scan --[no-]flip --flip-skip RE --soft-width --wrap-prefer --lm-pitch --debug-shader uvgrid --debug-lm class)")
        end
        i += 1
    end
    t0 = time()
    orig = Bsp(find_bsp(root, map))
    @printf("  [%6.2fs] load bsp\n", time() - t0)
    bv = Bevel(orig, a)
    @printf("  [%6.2fs] init bevel\n", time() - t0)
    new = nobevel ? orig : run!(bv)
    @printf("  [%6.2fs] run! done\n", time() - t0)
    new_prelim = new
    t1 = time()
    if smooth !== nothing
        new = smooth_trisoup(new, smooth)
        new = smooth_brush_props(new)
        @printf("  [%6.2fs] smoothing\n", time() - t1)
    end
    if !nobevel
        lm_diag!(bv)
        dump !== nothing && dump_near(bv, dump[1], dump[2])
        probe !== nothing && (length(probe) == 5 || error("--probe-spot needs \"x y z yaw pitch\"")) && probe_spot(bv, probe, fan)
        report !== nothing && write_seam_report(bv, report)
        scan && hole_scan(bv, orig, new_prelim)
    end
    (!nobevel && (stats || pk3 === nothing)) && (print_stats(bv); print_lm_diag(bv))
    tw = time()
    bspdata = pk3 !== nothing ? write_bsp(new) : UInt8[]
    pk3 !== nothing && @printf("  [%6.2fs] write_bsp\n", time() - tw)
    pk3 !== nothing && write_pk3(root, pk3, map, bspdata)
    pk3 !== nothing && @printf("  [%6.2fs] write_pk3 incl. zip\n", time() - tw)
    @printf("total %.2fs\n", time() - t0)
    return 0
end
