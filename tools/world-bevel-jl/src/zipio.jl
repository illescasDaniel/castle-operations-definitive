# Minimal zip reader/writer on top of the system zlib (Zlib_jll is a Julia standard library artifact, no extra install).
# Only what pk3 files need: stored/deflate entries, no zip64, no encryption.

struct ZStream
    next_in::Ptr{UInt8}
    avail_in::Cuint
    total_in::Culong
    next_out::Ptr{UInt8}
    avail_out::Cuint
    total_out::Culong
    msg::Ptr{UInt8}
    state::Ptr{Cvoid}
    zalloc::Ptr{Cvoid}
    zfree::Ptr{Cvoid}
    opaque::Ptr{Cvoid}
    data_type::Cint
    adler::Culong
    reserved::Culong
end
ZStream() = ZStream(C_NULL, 0, 0, C_NULL, 0, 0, C_NULL, C_NULL, C_NULL, C_NULL, C_NULL, 0, 0, 0)

zlib_version() = ccall((:zlibVersion, Zlib_jll.libz), Cstring, ())

function raw_inflate(src::AbstractVector{UInt8}, usize::Integer)
    out = Vector{UInt8}(undef, usize)
    zs = Ref(ZStream())
    rc = ccall((:inflateInit2_, Zlib_jll.libz), Cint, (Ref{ZStream}, Cint, Cstring, Cint), zs, -15, zlib_version(), sizeof(ZStream))
    rc == 0 || error("inflateInit2 failed ($rc)")
    GC.@preserve src out begin
        z = zs[]
        zs[] = ZStream(pointer(src), length(src), 0, pointer(out), usize, 0, C_NULL, z.state, z.zalloc, z.zfree, z.opaque, 0, 0, 0)
        rc = ccall((:inflate, Zlib_jll.libz), Cint, (Ref{ZStream}, Cint), zs, 4)  # Z_FINISH
        ccall((:inflateEnd, Zlib_jll.libz), Cint, (Ref{ZStream},), zs)
        rc == 1 || error("inflate failed ($rc)")
    end
    out
end

function raw_deflate(src::AbstractVector{UInt8}; level=9)
    zs = Ref(ZStream())
    rc = ccall((:deflateInit2_, Zlib_jll.libz), Cint, (Ref{ZStream}, Cint, Cint, Cint, Cint, Cint, Cstring, Cint),
               zs, level, 8, -15, 8, 0, zlib_version(), sizeof(ZStream))
    rc == 0 || error("deflateInit2 failed ($rc)")
    cap = Int(ccall((:deflateBound, Zlib_jll.libz), Culong, (Ref{ZStream}, Culong), zs, length(src))) + 64
    out = Vector{UInt8}(undef, cap)
    GC.@preserve src out begin
        z = zs[]
        zs[] = ZStream(pointer(src), length(src), 0, pointer(out), cap, 0, C_NULL, z.state, z.zalloc, z.zfree, z.opaque, 0, 0, 0)
        rc = ccall((:deflate, Zlib_jll.libz), Cint, (Ref{ZStream}, Cint), zs, 4)
        n = Int(zs[].total_out)
        ccall((:deflateEnd, Zlib_jll.libz), Cint, (Ref{ZStream},), zs)
        rc == 1 || error("deflate failed ($rc)")
        resize!(out, n)
    end
    out
end

crc32(data::AbstractVector{UInt8}) = GC.@preserve data UInt32(ccall((:crc32, Zlib_jll.libz), Culong, (Culong, Ptr{UInt8}, Cuint), 0, pointer(data), length(data)))

struct ZipEntry
    name::String
    method::UInt16
    csize::UInt32
    usize::UInt32
    offset::UInt32
end

le16(b, o) = UInt16(b[o+1]) | UInt16(b[o+2]) << 8
le32(b, o) = UInt32(b[o+1]) | UInt32(b[o+2]) << 8 | UInt32(b[o+3]) << 16 | UInt32(b[o+4]) << 24

function zip_entries(path::AbstractString)
    open(path) do io
        sz = filesize(path)
        tail = min(sz, 70000)
        seek(io, sz - tail)
        buf = read(io, tail)
        p = 0
        for i in length(buf)-21:-1:1
            if buf[i] == 0x50 && buf[i+1] == 0x4b && buf[i+2] == 0x05 && buf[i+3] == 0x06
                p = i
                break
            end
        end
        p == 0 && error("$path: no end of central directory")
        n = Int(le16(buf, p + 9))
        csz = Int(le32(buf, p + 11))
        cofs = Int(le32(buf, p + 15))
        seek(io, cofs)
        cd = read(io, csz)
        ents = ZipEntry[]
        o = 0
        for _ in 1:n
            le32(cd, o) == 0x02014b50 || error("$path: bad central directory")
            method = le16(cd, o + 10)
            cs = le32(cd, o + 20)
            us = le32(cd, o + 24)
            nl, el, cl = Int(le16(cd, o + 28)), Int(le16(cd, o + 30)), Int(le16(cd, o + 32))
            off = le32(cd, o + 42)
            name = String(cd[o+47:o+46+nl])
            push!(ents, ZipEntry(name, method, cs, us, off))
            o += 46 + nl + el + cl
        end
        ents
    end
end

function zip_read(path::AbstractString, e::ZipEntry)
    open(path) do io
        seek(io, e.offset)
        h = read(io, 30)
        nl, el = Int(le16(h, 26)), Int(le16(h, 28))
        skip(io, nl + el)
        data = read(io, e.csize)
        e.method == 0 && return data
        e.method == 8 && return raw_inflate(data, e.usize)
        error("$path: unsupported zip method $(e.method)")
    end
end

# 2020-01-01 00:00:00 like the Python tool (reproducible archives)
const DOS_TIME = 0x0000
const DOS_DATE = UInt16(((2020 - 1980) << 9) | (1 << 5) | 1)

function zip_write(path::AbstractString, files::Vector{Pair{String,Vector{UInt8}}})
    mkpath(dirname(abspath(path)))
    out = IOBuffer()
    cd = IOBuffer()
    w16(io, x) = write(io, htol(UInt16(x)))
    w32(io, x) = write(io, htol(UInt32(x)))
    for (name, data) in files
        comp = raw_deflate(data)
        crc = crc32(data)
        off = position(out)
        nb = Vector{UInt8}(name)
        w32(out, 0x04034b50); w16(out, 20); w16(out, 0); w16(out, 8); w16(out, DOS_TIME); w16(out, DOS_DATE)
        w32(out, crc); w32(out, length(comp)); w32(out, length(data)); w16(out, length(nb)); w16(out, 0)
        write(out, nb); write(out, comp)
        w32(cd, 0x02014b50); w16(cd, 20); w16(cd, 20); w16(cd, 0); w16(cd, 8); w16(cd, DOS_TIME); w16(cd, DOS_DATE)
        w32(cd, crc); w32(cd, length(comp)); w32(cd, length(data)); w16(cd, length(nb)); w16(cd, 0); w16(cd, 0)
        w16(cd, 0); w16(cd, 0); w32(cd, 0); w32(cd, off); write(cd, nb)
    end
    cdpos = position(out)
    cdb = take!(cd)
    write(out, cdb)
    w32(out, 0x06054b50); w16(out, 0); w16(out, 0); w16(out, length(files)); w16(out, length(files))
    w32(out, length(cdb)); w32(out, cdpos); w16(out, 0)
    write(path, take!(out))
end

# --- MD4 (Com_BlockChecksum for the AAS bspchecksum) ---------------------------------------------------------------
@inline rol32(x::UInt32, n) = (x << n) | (x >> (32 - n))

function md4(data::AbstractVector{UInt8})
    len = length(data)
    padlen = (55 - len) % 64
    padlen < 0 && (padlen += 64)
    msg = Vector{UInt8}(undef, len + 1 + padlen + 8)
    copyto!(msg, 1, data, 1, len)
    msg[len+1] = 0x80
    fill!(view(msg, len+2:len+1+padlen), 0x00)
    bits = UInt64(len) * 8
    for i in 0:7
        msg[len+1+padlen+1+i] = UInt8((bits >> (8i)) & 0xff)
    end
    a0, b0, c0, d0 = 0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476
    X = Vector{UInt32}(undef, 16)
    sh1 = (3, 7, 11, 19); sh2 = (3, 5, 9, 13); sh3 = (3, 9, 11, 15)
    k3 = (0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15)
    for off in 0:64:length(msg)-64
        for i in 1:16
            X[i] = le32(msg, off + 4(i - 1))
        end
        a, b, c, d = a0, b0, c0, d0
        for i in 0:15
            t = a + ((b & c) | (~b & d)) + X[i+1]
            a, b, c, d = d, rol32(t, sh1[i%4+1]), b, c
        end
        for i in 0:15
            k = (i % 4) * 4 + i ÷ 4
            t = a + ((b & c) | (b & d) | (c & d)) + X[k+1] + 0x5a827999
            a, b, c, d = d, rol32(t, sh2[i%4+1]), b, c
        end
        for i in 0:15
            t = a + (b ⊻ c ⊻ d) + X[k3[i+1]+1] + 0x6ed9eba1
            a, b, c, d = d, rol32(t, sh3[i%4+1]), b, c
        end
        a0 += a; b0 += b; c0 += c; d0 += d
    end
    (a0, b0, c0, d0)
end

block_checksum(data) = (w = md4(data); w[1] ⊻ w[2] ⊻ w[3] ⊻ w[4])

aas_checksum(aas) = le32(UInt8[aas[9+i] ⊻ UInt8((i * 119) & 0xff) for i in 0:3], 0)

function patch_aas(aas::Vector{UInt8}, chk::UInt32)
    out = copy(aas)
    for i in 0:3
        out[9+i] = UInt8((chk >> (8i)) & 0xff) ⊻ UInt8((i * 119) & 0xff)
    end
    out
end
