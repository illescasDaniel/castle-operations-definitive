#!/usr/bin/env python3
"""RTCW MDC (compressed vertex-animated model: weapons, heads, props) smoothing: one Loop level, normal displacement only.

Same idea as model_smooth.py (MDS), but the models have no skeleton: every frame is decoded to float positions, the
same sparse stencil is applied to every frame and the result is written with every frame as an uncompressed base frame
(numCompFrames 0). Tags, frame bounds, shaders and UVs of the original vertices are kept. Output is derived from the
owned game paks (run/main/pak0.pk3): private, never commit or redistribute.

  python3 -I tools/model-smooth/mdc_smooth.py --stats 'models/weapons2/*'
  python3 -I tools/model-smooth/mdc_smooth.py --smooth 'models/weapons2/*' --pk3 run/codmod/codmod_smooth_mdc.pk3
  python3 -I tools/model-smooth/mdc_smooth.py --obj models/weapons2/colt/v_colt.mdc --out c.obj [--frame N] [--smoothed]

Format (qcommon/qfiles.h, rend2 tr_model.c): a compressed frame is its base frame's position plus an 8-bit-per-axis offset
(scale 0.05, bias 127) and an 8-bit normal index into anorms256.h; base frames are int16 xyz (1/64) + lat/long normal.
"""
import argparse, collections, fnmatch, math, re, struct, sys, zipfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PAK = ROOT / "run/main/pak0.pk3"
SHADER_MAX_VERTEXES = 4000
SHADER_MAX_INDEXES = 6 * SHADER_MAX_VERTEXES
MDC_IDENT = 0x43504449  # 'IDPC' read little endian: bytes "IDPC"
HDR = struct.Struct("<4si64s10i")  # ident version name flags numFrames numTags numSurfaces numSkins ofsFrames ofsTagNames ofsTags ofsSurfaces ofsEnd
SURF = struct.Struct("<4s64s14i")  # ident name flags numComp numBase numShaders numVerts numTris ofsTris ofsShaders ofsSt ofsXyzN ofsXyzC ofsFrameBase ofsFrameComp ofsEnd


def anormals():
    s = (ROOT / "iortcw/SP/code/rend2/anorms256.h").read_text()
    body = s[s.rindex("*/"):]
    v = np.array(re.findall(r"-?\d*\.\d+", body), np.float64).reshape(-1, 3)
    assert len(v) == 256
    return v


ANORM = None


def decode_normals(codes):
    lat = ((codes >> 8) & 0xFF) * (2 * math.pi / 256)
    lng = (codes & 0xFF) * (2 * math.pi / 256)
    return np.stack([np.cos(lat) * np.sin(lng), np.sin(lat) * np.sin(lng), np.cos(lng)], axis=-1)


def encode_normals(n):
    n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)
    lat = np.rint(np.arctan2(n[..., 1], n[..., 0]) * (256 / (2 * math.pi))).astype(np.int64) & 0xFF
    lng = np.rint(np.arccos(np.clip(n[..., 2], -1, 1)) * (256 / (2 * math.pi))).astype(np.int64) & 0xFF
    return ((lat << 8) | lng).astype("<i2") if False else (((lat << 8) | lng) & 0xFFFF).astype("<u2").view("<i2")


class Surf:
    pass


def parse_mdc(d):
    global ANORM
    if ANORM is None:
        ANORM = anormals()
    ident, ver, name, flags, nf, nt, ns, nsk, ofs_fr, ofs_tn, ofs_tg, ofs_s, ofs_end = HDR.unpack_from(d, 0)
    assert ident == b"IDPC" and ver == 2, (ident, ver)
    surfs = []
    o = ofs_s
    for _ in range(ns):
        (sid, sname, sflags, ncomp, nbase, nsh, nv, ntri, o_tri, o_sh, o_st, o_xn, o_xc, o_fb, o_fc, o_end) = SURF.unpack_from(d, o)
        s = Surf()
        s.head = d[o:o + SURF.size]
        s.name = sname.split(b"\0")[0].decode("latin-1")
        s.flags, s.nsh, s.nv, s.ntri = sflags, nsh, nv, ntri
        s.shaders = d[o + o_sh:o + o_sh + 68 * nsh]
        s.tris = np.frombuffer(d, "<i4", ntri * 3, o + o_tri).reshape(-1, 3)
        s.st = np.frombuffer(d, "<f4", nv * 2, o + o_st).reshape(-1, 2)
        xn = np.frombuffer(d, "<i2", nv * nbase * 4, o + o_xn).reshape(nbase, nv, 4)
        fb = np.frombuffer(d, "<i2", nf, o + o_fb)
        fc = np.frombuffer(d, "<i2", nf, o + o_fc)
        P = np.empty((nf, nv, 3))
        N = np.empty((nf, nv, 3))
        base_pos = xn[:, :, :3].astype(np.float64) / 64.0
        base_nrm = decode_normals(xn[:, :, 3].astype(np.int64) & 0xFFFF)
        comp = np.frombuffer(d, "<u4", nv * ncomp, o + o_xc).reshape(ncomp, nv) if ncomp else None
        for f in range(nf):
            P[f] = base_pos[fb[f]]
            N[f] = base_nrm[fb[f]]
            if fc[f] >= 0:
                c = comp[fc[f]]
                P[f] += (np.stack([c & 255, (c >> 8) & 255, (c >> 16) & 255], -1).astype(np.float64) - 127.0) * 0.05
                N[f] = ANORM[(c >> 24) & 255]
        s.P, s.N = P, N
        surfs.append(s)
        o += o_end
    m = Surf()
    m.d, m.nf, m.nt, m.surfs, m.ofs_s, m.ofs_end = d, nf, nt, surfs, ofs_s, ofs_end
    return m


def write_surface(s, P, N, st, tris):
    nf, nv = P.shape[0], P.shape[1]
    q = np.zeros((nf, nv, 4), "<i2")
    q[:, :, :3] = np.clip(np.rint(P * 64.0), -32768, 32767).astype("<i2")
    q[:, :, 3] = encode_normals(N)
    h = list(SURF.unpack(s.head))
    out = bytearray(SURF.size)
    parts = [("sh", s.shaders), ("tri", tris.astype("<i4").tobytes()), ("st", st.astype("<f4").tobytes()), ("xn", q.tobytes()),
             ("xc", b""), ("fb", np.arange(nf, dtype="<i2").tobytes()), ("fc", np.full(nf, -1, "<i2").tobytes())]
    offs = {}
    for k, b in parts:
        offs[k] = len(out)
        out += b
        out += b"\0" * (-len(out) % 4)
    h[3], h[4], h[5], h[6] = 0, nf, s.nsh, nv  # flags numComp numBase numShaders numVerts: h indexes after ident,name
    return out, offs, nv, len(tris)


def pack_surface(s, P, N, st, tris):
    nf, nv = P.shape[0], P.shape[1]
    out, offs, nv, nt = write_surface(s, P, N, st, tris)
    ident, name, flags, ncomp, nbase, nsh, _nv, _nt, *_ = SURF.unpack(s.head)
    hdr = SURF.pack(ident, name, flags, 0, nf, nsh, nv, nt, offs["tri"], offs["sh"], offs["st"], offs["xn"], offs["xc"], offs["fb"], offs["fc"], len(out))
    out[:SURF.size] = hdr
    return bytes(out)


# ------------------------------------------------------------------------------------------------ smoothing
class Opts:
    crease_angle = 90.0


def smooth_surface(s, o=Opts):
    P, N, tris, uv = s.P, s.N, s.tris.astype(np.int64), s.st
    F, n = P.shape[0], P.shape[1]
    T = len(tris)
    info = dict(before_v=n, before_t=T, after_v=n, after_t=T, changed=False, reason="")
    if 4 * T > SHADER_MAX_INDEXES // 3 or n + 3 * T // 2 + 8 > SHADER_MAX_VERTEXES:
        # worst case new verts = edges; checked exactly below
        pass
    # weld vertices that coincide in every frame
    q = np.rint(P * 64.0).astype(np.int32).transpose(1, 0, 2).reshape(n, -1)
    keys = {}
    wel = np.empty(n, np.int64)
    for i in range(n):
        wel[i] = keys.setdefault(q[i].tobytes(), len(keys))
    nt_ = len(keys)
    rep = np.empty(nt_, np.int64)
    rep[wel[::-1]] = np.arange(n)[::-1]
    tp = P[:, rep]  # (F,nt,3)
    tt = wel[tris]
    newv, tri_keys = {}, []
    for k in range(T):
        c = tris[k]
        ks = []
        for p, qq in ((c[0], c[1]), (c[1], c[2]), (c[2], c[0])):
            key = (int(min(p, qq)), int(max(p, qq)))
            if key not in newv:
                newv[key] = [len(newv), (int(wel[p]), int(wel[qq]))]
            ks.append(key)
        tri_keys.append(ks)
    nv_out, nt_out = n + len(newv), 4 * T
    if nv_out > SHADER_MAX_VERTEXES or nt_out * 3 > SHADER_MAX_INDEXES:
        info["reason"] = "too big (%d verts, %d tris)" % (nv_out, nt_out)
        return None, info
    edges = {}
    for k in range(T):
        a, b, c = (int(x) for x in tt[k])
        for u, v, opp in ((a, b, c), (b, c, a), (c, a, b)):
            if u != v:
                edges.setdefault((u, v) if u < v else (v, u), []).append((k, opp, (u, v)))
    fn = np.cross(tp[0][tt[:, 1]] - tp[0][tt[:, 0]], tp[0][tt[:, 2]] - tp[0][tt[:, 0]])
    ln = np.linalg.norm(fn, axis=1)
    fnu = fn / np.maximum(ln, 1e-12)[:, None]
    cos_c = math.cos(math.radians(o.crease_angle))
    ecls = {}
    for e, lst in edges.items():
        if len(lst) == 1:
            ecls[e] = "B"
        elif len(lst) > 2:
            ecls[e] = "C"
        else:
            (k1, _, d1), (k2, _, d2) = lst
            ecls[e] = "C" if d1 == d2 or (ln[k1] > 1e-9 and ln[k2] > 1e-9 and float(fnu[k1] @ fnu[k2]) < cos_c) else "S"
    nb = [[] for _ in range(nt_)]
    for (a, b), c in ecls.items():
        nb[a].append((b, c)); nb[b].append((a, c))
    vst = []
    for t in range(nt_):
        cl = [x for x in nb[t] if x[1] == "C"]
        if any(c == "B" for _, c in nb[t]) or not nb[t]:
            vst.append(None)
        elif len(cl) == 2:
            vst.append({t: 0.75, cl[0][0]: 0.125, cl[1][0]: 0.125})
        elif len(cl) != 0 or len(nb[t]) < 3:
            vst.append(None)
        else:
            m = len(nb[t])
            beta = 3.0 / 16 if m == 3 else 3.0 / (8 * m)
            st = {t: 1 - m * beta}
            for oo, _ in nb[t]:
                st[oo] = beta
            vst.append(st)

    # per-frame topology normals (area weighted face normals), sign calibrated against the stored normals
    acc = np.zeros((F, nt_, 3))
    for f in range(F):
        c = np.cross(tp[f][tt[:, 1]] - tp[f][tt[:, 0]], tp[f][tt[:, 2]] - tp[f][tt[:, 0]])
        for j in range(3):
            np.add.at(acc[f], tt[:, j], c)
    sign = -1.0 if float((acc[0][wel] * N[0]).sum()) < 0 else 1.0
    an = np.linalg.norm(acc, axis=2, keepdims=True)
    fb = N[:, rep]
    tn = np.where(an > 1e-9, sign * acc / np.maximum(an, 1e-12), fb)

    def proj(d, nrm):
        return (d * nrm).sum(-1, keepdims=True) * nrm

    ev_disp = np.zeros((F, nt_, 3))
    for t in range(nt_):
        if vst[t] is not None:
            loop = sum(a * tp[:, i] for i, a in vst[t].items())
            ev_disp[:, t] = proj(loop - tp[:, t], tn[:, t])
    order = sorted(newv.items(), key=lambda kv: kv[1][0])
    no = len(order)
    odd = np.empty((F, no, 3))
    for key, (r, (a_, b_)) in order:
        mid = 0.5 * (tp[:, a_] + tp[:, b_])
        smooth = a_ != b_ and ecls.get((min(a_, b_), max(a_, b_))) == "S"
        if smooth:
            opp = [x[1] for x in edges[(min(a_, b_), max(a_, b_))]]
            st = {}
            for t_, c_ in ((a_, 0.375), (b_, 0.375), (opp[0], 0.125), (opp[1], 0.125)):
                st[t_] = st.get(t_, 0.0) + c_
            loop = sum(a * tp[:, i] for i, a in st.items())
            on = tn[:, a_] + tn[:, b_]
            onl = np.linalg.norm(on, axis=1, keepdims=True)
            on = np.where(onl > 1e-3, on / np.maximum(onl, 1e-12), 0.0)
            odd[:, r] = mid + proj(loop - mid, on)
        else:
            odd[:, r] = mid
    Pn = np.concatenate([P + ev_disp[:, wel], odd], axis=1)
    pv = np.array([[k[0], k[1]] for k, _ in order]).reshape(-1, 2)
    nn = N[:, pv[:, 0]] + N[:, pv[:, 1]] if no else np.zeros((F, 0, 3))
    nl = np.linalg.norm(nn, axis=2, keepdims=True)
    nn = np.where(nl > 1e-6, nn / np.maximum(nl, 1e-12), N[:, pv[:, 0]] if no else nn)
    Nn = np.concatenate([N, nn], axis=1)
    uvn = np.concatenate([uv, (uv[pv[:, 0]] + uv[pv[:, 1]]) * 0.5], axis=0) if no else uv
    idx = {key: n + r for key, (r, _) in order}
    ot = np.empty((T * 4, 3), np.int64)
    for k in range(T):
        c0, c1, c2 = (int(x) for x in tris[k])
        m01, m12, m20 = (idx[kk] for kk in tri_keys[k])
        ot[4 * k:4 * k + 4] = ((c0, m01, m20), (c1, m12, m01), (c2, m20, m12), (m01, m12, m20))
    info.update(changed=True, pv=pv, after_v=nv_out, after_t=nt_out, maxdisp=float(np.abs(Pn[:, :n] - P).max()))
    return (Pn, Nn, uvn, ot), info


def smooth_model(m, name=""):
    """Smooth every surface. Heads (name contains '/head'): small helper surfaces (teeth, eyelids, mouth) are not
    subdivided; they ride on the displacement of the nearest vertex of the main surface so they do not poke through."""
    out, infos = [], []
    head = "/head" in name
    big = max(range(len(m.surfs)), key=lambda i: len(m.surfs[i].tris)) if m.surfs else 0
    res = [None] * len(m.surfs)
    for i, s in enumerate(m.surfs):
        if "flash" in name or len(s.tris) < 8:  # muzzle flashes and tag stubs: keep as is
            infos.append(dict(before_v=s.nv, before_t=len(s.tris), after_v=s.nv, after_t=len(s.tris), changed=False, reason="flash/stub"))
        elif head and i != big and len(s.tris) <= 40:
            infos.append(dict(before_v=s.nv, before_t=len(s.tris), after_v=s.nv, after_t=len(s.tris), changed=False, reason="head helper (rides)"))
        else:
            res[i], info = smooth_surface(s)
            infos.append(info)
    for i, s in enumerate(m.surfs):
        r = res[i]
        if r is not None:
            P, N, uv, tris = r
        else:
            P, N, uv, tris = s.P, s.N, s.st, s.tris
            if head and i != big and infos[i]["reason"].startswith("head helper") and res[big] is not None:
                b = m.surfs[big]
                disp = res[big][0][:, :b.nv] - b.P
                near = np.argmin(((s.P[0][:, None, :] - b.P[0][None]) ** 2).sum(-1), axis=1)
                P = s.P + disp[:, near]
        out.append(pack_surface(s, P, N, uv, np.asarray(tris)))
    d = m.d
    body = bytearray(d[:m.ofs_s])
    for b in out:
        body += b
    h = list(HDR.unpack_from(d, 0))
    h[-1] = len(body)
    body[:HDR.size] = HDR.pack(*h)
    return bytes(body), infos


# ------------------------------------------------------------------------------------------------ CLI
DEFAULT_EXCLUDE = "models/mapobjects/tree/*,models/mapobjects/plants/*,models/mapobjects/sky/*,models/mapobjects/ui/*,models/mapobjects/bjui/*,models/shards/*,models/weapons2/*/v_*_barrel*,models/weapons2/colt*/v_*,models/weapons2/luger/v_*"


def load_files(pattern, exclude=""):
    z = zipfile.ZipFile(PAK)
    pats = pattern.split(",")
    exc = [e for e in exclude.split(",") if e]
    return {n: z.read(n) for n in z.namelist()
            if n.endswith(".mdc") and any(fnmatch.fnmatch(n, p if p.endswith("mdc") else p + "*.mdc") or fnmatch.fnmatch(n, p) for p in pats)
            and not any(fnmatch.fnmatch(n, e) for e in exc)}


def cmd_stats(pattern):
    files = load_files(pattern)
    tv0 = tv1 = 0
    for n, d in sorted(files.items()):
        m = parse_mdc(d)
        for s in m.surfs:
            r, info = smooth_surface(s)
            tv0 += info["before_v"]; tv1 += info["after_v"]
            print("%-48s %-16s frames %3d verts %5d -> %5d tris %5d -> %5d %s maxdisp %.2f" % (
                n, s.name[:16], m.nf, info["before_v"], info["after_v"], info["before_t"], info["after_t"], info["reason"], info.get("maxdisp", 0)))
    print("%d models, verts %d -> %d" % (len(files), tv0, tv1))


def cmd_smooth(pattern, pk3, exclude=DEFAULT_EXCLUDE):
    files = load_files(pattern, exclude)
    if not files:
        sys.exit("no MDC matches")
    Path(pk3).parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    with zipfile.ZipFile(pk3, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in sorted(files.items()):
            b, infos = smooth_model(parse_mdc(d), n)
            z.writestr(n, b)
            kept += sum(1 for i in infos if not i["changed"])
            for i in infos:
                if not i["changed"]:
                    print("  KEPT %s: %s" % (n, i["reason"]))
    print("%d models smoothed (%d surfaces kept); wrote %s" % (len(files), kept, pk3))


def cmd_obj(path, out, frame, smoothed):
    d = load_files(path).get(path)
    if d is None:
        sys.exit("model not found")
    m = parse_mdc(d)
    lines, base = [], 1
    for s in m.surfs:
        P, uv, tris = s.P[frame], s.st, s.tris
        if smoothed:
            r, _ = smooth_surface(s)
            if r is not None:
                P, uv, tris = r[0][frame], r[2], r[3]
        lines.append("o " + s.name)
        lines += ["v %f %f %f" % tuple(p) for p in P]
        lines += ["f %d %d %d" % tuple(int(x) + base for x in t) for t in tris]
        base += len(P)
    Path(out).write_text("\n".join(lines) + "\n")
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stats", metavar="GLOB")
    ap.add_argument("--smooth", metavar="GLOB")
    ap.add_argument("--pk3", default=str(ROOT / "run/codmod/codmod_smooth_mdc.pk3"))
    ap.add_argument("--exclude", default=DEFAULT_EXCLUDE, help="comma separated globs skipped by --smooth (foliage cards, sky, UI, shards)")
    ap.add_argument("--obj", metavar="MODEL")
    ap.add_argument("--out")
    ap.add_argument("--frame", type=int, default=0)
    ap.add_argument("--smoothed", action="store_true")
    a = ap.parse_args()
    if a.stats is not None:
        cmd_stats(a.stats)
    elif a.smooth is not None:
        cmd_smooth(a.smooth, a.pk3, a.exclude)
    elif a.obj:
        cmd_obj(a.obj, a.out or "out.obj", a.frame, a.smoothed)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
