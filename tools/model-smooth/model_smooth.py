#!/usr/bin/env python3
"""RTCW MDS (skeletal model) toolkit: lossless reader/writer, pose evaluation, stats, OBJ dump.

Stage 0/1 of the "smooth character models" project (Loop subdivision that keeps skin weights exact). Reads the owned
game paks in run/main/. Outputs (OBJ files, reports) are derived from proprietary assets: never commit or redistribute.

  python3 -I tools/model-smooth/model_smooth.py --roundtrip
  python3 -I tools/model-smooth/model_smooth.py --stats [GLOB]
  python3 -I tools/model-smooth/model_smooth.py --obj models/players/infantryss/body.mds --out f0.obj [--frame N]

Format notes (verified against iortcw rend2 tr_model.c / tr_animation.c and the 32 stock files):
  * v4 header has no LOD table: a model is ONE surface list; LOD is per surface (minLod + collapseMap). `lods` is
    kept as a list with a single entry for forward compatibility.
  * mdsWeight_t.boneIndex is a GLOBAL bone index (the renderer does bones[w->boneIndex]); boneReferences is only the
    set of bones a surface needs (sorted ascending, includes ancestors).
  * file layout is frames, bones, surfaces, tags; inside a surface: header, verts, triangles, collapseMap, boneRefs.
    The writer recomputes offsets from content; it refuses to write a layout it cannot reproduce byte-identically.
"""
import argparse, collections, fnmatch, math, struct, sys, zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PAKS = [ROOT / "run/main" / n for n in ("pak0.pk3",)]

MDS_IDENT = 0x5753444D  # ('W'<<24)+('S'<<16)+('D'<<8)+'M'
MDS_VERSION = 4
MDS_MAX_VERTS = 6000
MDS_MAX_TRIANGLES = 8192
SHADER_MAX_VERTEXES = 4000

HDR = struct.Struct("<ii64sff10i")  # ident version name lodScale lodBias numFrames numBones ofsFrames ofsBones
# torsoParent numSurfaces ofsSurfaces numTags ofsTags ofsEnd
HDR_SIZE = HDR.size  # 120
SURF = struct.Struct("<i64s64s" + "i" * 11)  # ident name shader shaderIndex minLod ofsHeader numVerts ofsVerts numTris
# ofsTris ofsCollapse numBoneRefs ofsBoneRefs ofsEnd
SURF_SIZE = SURF.size  # 176
VHEAD = np.dtype([("n", "<f4", 3), ("uv", "<f4", 2), ("nw", "<i4"), ("fp", "<i4"), ("fd", "<f4")])  # 32 bytes
WDT = np.dtype([("b", "<i4"), ("w", "<f4"), ("o", "<f4", 3)])  # 20 bytes
BONE_INFO_SIZE = 80  # name[64] parent torsoWeight parentDist flags
TAG_SIZE = 72  # name[64] torsoWeight boneIndex


def _cstr(b):
    return b.split(b"\0", 1)[0].decode("latin-1")


# ---------------------------------------------------------------------------------------------- data model
@dataclass
class MDSSurface:
    ident: int
    name_raw: bytes  # 64 raw bytes (kept verbatim for byte-identical output)
    shader_raw: bytes
    shaderIndex: int
    minLod: int
    normals: np.ndarray  # (N,3) f32
    uvs: np.ndarray  # (N,2) f32
    fixedParent: np.ndarray  # (N,) i32
    fixedDist: np.ndarray  # (N,) f32
    wcount: np.ndarray  # (N,) i32 weights per vertex
    weights: np.ndarray  # (W,) WDT: flat, vertex i owns wstart[i] : wstart[i]+wcount[i]
    triangles: np.ndarray  # (T,3) i32
    collapseMap: np.ndarray  # (N,) i32
    boneRefs: np.ndarray  # (R,) i32

    @property
    def name(self):
        return _cstr(self.name_raw)

    @property
    def shader(self):
        return _cstr(self.shader_raw)

    @property
    def numVerts(self):
        return len(self.normals)

    @property
    def numTris(self):
        return len(self.triangles)

    @property
    def wstart(self):
        return np.concatenate([[0], np.cumsum(self.wcount)]).astype(np.int64)

    def vert_weights(self, i):
        """[(boneIndex, weight, offset(3,))] of vertex i."""
        s = self.wstart
        return [(int(w["b"]), float(w["w"]), w["o"].copy()) for w in self.weights[s[i]:s[i + 1]]]

    def weight_lists(self):
        s = self.wstart
        return [[(int(w["b"]), float(w["w"]), w["o"].copy()) for w in self.weights[s[i]:s[i + 1]]]
                for i in range(self.numVerts)]


@dataclass
class MDSModel:
    ident: int
    version: int
    name_raw: bytes
    lodScale: float
    lodBias: float
    numFrames: int
    numBones: int
    torsoParent: int
    frames_raw: bytes  # numFrames * (52 + 12*numBones)
    bones_raw: bytes  # numBones * 80
    tags_raw: bytes  # numTags * 72
    numTags: int
    lods: list = field(default_factory=list)  # [[MDSSurface, ...]]  (v4 has exactly one)

    @property
    def name(self):
        return _cstr(self.name_raw)

    @property
    def surfaces(self):
        return self.lods[0]

    @property
    def frame_size(self):
        return 52 + 12 * self.numBones

    def bone_info(self):
        """[(name, parent, torsoWeight, parentDist, flags)]"""
        out = []
        for i in range(self.numBones):
            n, p, tw, pd, fl = struct.unpack_from("<64siffi", self.bones_raw, i * BONE_INFO_SIZE)
            out.append((_cstr(n), p, tw, pd, fl))
        return out

    def tags(self):
        return [(_cstr(self.tags_raw[i * TAG_SIZE:i * TAG_SIZE + 64]),) + struct.unpack_from("<fi", self.tags_raw, i * TAG_SIZE + 64)
                for i in range(self.numTags)]

    def frame(self, i):
        """(bounds(2,3), localOrigin(3), radius, parentOffset(3), shorts(numBones,6) int16)"""
        off = i * self.frame_size
        f = np.frombuffer(self.frames_raw, "<f4", 13, off)
        sh = np.frombuffer(self.frames_raw, "<i2", self.numBones * 6, off + 52).reshape(self.numBones, 6)
        return f[0:6].reshape(2, 3), f[6:9], float(f[9]), f[10:13], sh


# ---------------------------------------------------------------------------------------------- parse / write
def _parse_surface(d, base):
    (ident, name, shader, shaderIndex, minLod, ofsHeader, nv, ofsV, nt, ofsT, ofsC, nbr, ofsB, ofsEnd) = SURF.unpack_from(d, base)
    if ofsHeader != -base:
        raise ValueError("surface ofsHeader %d != %d" % (ofsHeader, -base))
    normals = np.empty((nv, 3), "<f4"); uvs = np.empty((nv, 2), "<f4")
    fp = np.empty(nv, "<i4"); fd = np.empty(nv, "<f4"); wc = np.empty(nv, "<i4")
    chunks = []
    p = base + ofsV
    for i in range(nv):
        h = np.frombuffer(d, VHEAD, 1, p)[0]
        nw = int(h["nw"])
        normals[i] = h["n"]; uvs[i] = h["uv"]; wc[i] = nw; fp[i] = h["fp"]; fd[i] = h["fd"]
        chunks.append(np.frombuffer(d, WDT, nw, p + 32))
        p += 32 + 20 * nw
    if p != base + ofsT:
        raise ValueError("vertex block not followed directly by triangles (%d vs %d)" % (p, base + ofsT))
    weights = np.concatenate(chunks) if chunks else np.empty(0, WDT)
    tris = np.frombuffer(d, "<i4", nt * 3, base + ofsT).reshape(nt, 3).copy()
    if ofsC != ofsT + 12 * nt or ofsB != ofsC + 4 * nv or ofsEnd != ofsB + 4 * nbr:
        raise ValueError("unexpected surface sub-block layout")
    cm = np.frombuffer(d, "<i4", nv, base + ofsC).copy()
    br = np.frombuffer(d, "<i4", nbr, base + ofsB).copy()
    return MDSSurface(ident, name, shader, shaderIndex, minLod, normals, uvs, fp, fd, wc, weights.copy(), tris, cm, br)


def parse_mds(d):
    (ident, version, name, lodScale, lodBias, nF, nB, ofsF, ofsB, torso, nS, ofsS, nT, ofsT, ofsEnd) = HDR.unpack_from(d, 0)
    if ident != MDS_IDENT or version != MDS_VERSION:
        raise ValueError("not an MDS v4 file")
    fsz = 52 + 12 * nB
    if ofsF != HDR_SIZE or ofsB != ofsF + nF * fsz:
        raise ValueError("unexpected frames/bones layout")
    if ofsEnd != len(d):
        raise ValueError("ofsEnd != file size")
    surfs = []
    p = ofsS
    for _ in range(nS):
        s = _parse_surface(d, p)
        surfs.append(s)
        p = p + SURF.unpack_from(d, p)[-1]
    if p != ofsT or ofsB + nB * BONE_INFO_SIZE != ofsS or ofsT + nT * TAG_SIZE != ofsEnd:
        raise ValueError("unexpected block order/padding")
    return MDSModel(ident, version, name, lodScale, lodBias, nF, nB, torso, bytes(d[ofsF:ofsB]),
                    bytes(d[ofsB:ofsS]), bytes(d[ofsT:ofsEnd]), nT, [surfs])


def _write_surface(s, base):
    nv, nt, nbr = s.numVerts, s.numTris, len(s.boneRefs)
    vb = bytearray()
    ws = s.wstart
    for i in range(nv):
        h = np.zeros(1, VHEAD)
        h["n"] = s.normals[i]; h["uv"] = s.uvs[i]; h["nw"] = s.wcount[i]; h["fp"] = s.fixedParent[i]; h["fd"] = s.fixedDist[i]
        vb += h.tobytes() + s.weights[ws[i]:ws[i + 1]].tobytes()
    ofsV = SURF_SIZE
    ofsT = ofsV + len(vb)
    ofsC = ofsT + 12 * nt
    ofsB = ofsC + 4 * nv
    ofsEnd = ofsB + 4 * nbr
    head = SURF.pack(s.ident, s.name_raw, s.shader_raw, s.shaderIndex, s.minLod, -base, nv, ofsV, nt, ofsT, ofsC, nbr, ofsB, ofsEnd)
    return (head + bytes(vb) + s.triangles.astype("<i4").tobytes() + s.collapseMap.astype("<i4").tobytes()
            + s.boneRefs.astype("<i4").tobytes())


def write_mds(m):
    if len(m.lods) != 1:
        raise ValueError("MDS v4 has a single surface list")
    ofsF = HDR_SIZE
    ofsB = ofsF + len(m.frames_raw)
    ofsS = ofsB + len(m.bones_raw)
    body = bytearray()
    for s in m.lods[0]:
        body += _write_surface(s, ofsS + len(body))
    ofsT = ofsS + len(body)
    ofsEnd = ofsT + len(m.tags_raw)
    head = HDR.pack(m.ident, m.version, m.name_raw, m.lodScale, m.lodBias, m.numFrames, m.numBones,
                       ofsF, ofsB, m.torsoParent, len(m.lods[0]), ofsS, m.numTags, ofsT, ofsEnd)
    return head + m.frames_raw + m.bones_raw + bytes(body) + m.tags_raw


# ---------------------------------------------------------------------------------------------- pose / skinning
def _angle_vectors(pitch, yaw, roll):
    r = math.pi * 2 / 360
    sy, cy = math.sin(yaw * r), math.cos(yaw * r)
    sp, cp = math.sin(pitch * r), math.cos(pitch * r)
    sr, cr = math.sin(roll * r), math.cos(roll * r)
    fwd = np.array([cp * cy, cp * sy, -sp])
    right = np.array([-sr * sp * cy + cr * sy, -sr * sp * sy - cr * cy, -sr * cp])
    up = np.array([cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp])
    return fwd, right, up


def angles_to_axis(angles):
    """Engine AnglesToAxis: rows are forward, -right, up (mat[row][col])."""
    f, r, u = _angle_vectors(*angles)
    return np.array([f, -r, u])


def pose_frame(model, frame_index):
    """Port of R_CalcBone for one frame (no lerp, no torso blend). Returns (matrices (B,3,3), translations (B,3))."""
    _, _, _, parentOffset, sh = model.frame(frame_index)
    info = model.bone_info()
    k = 360.0 / 65536
    nb = model.numBones
    M = np.zeros((nb, 3, 3)); T = np.zeros((nb, 3)); done = [False] * nb

    def calc(b):
        if done[b]:
            return
        parent, pdist = info[b][1], info[b][3]
        M[b] = angles_to_axis(sh[b, 0:3] * k)
        if parent >= 0:
            calc(parent)
            f, _, _ = _angle_vectors(sh[b, 4] * k, sh[b, 5] * k, 0.0)  # ofsAngles pitch, yaw
            T[b] = T[parent] + pdist * f
        else:
            T[b] = parentOffset
        done[b] = True

    for b in range(nb):
        calc(b)
    return M, T


def skin_positions(wcount, weights, bones):
    """Skinned positions (N,3) of flat weight arrays (RB_SurfaceAnim sum of weight * (M @ offset + t))."""
    M, T = bones
    n = len(wcount)
    pos = np.zeros((n, 3))
    if len(weights) == 0:
        return pos
    vid = np.repeat(np.arange(n), wcount)
    b = weights["b"]
    contrib = np.einsum("wij,wj->wi", M[b], weights["o"].astype(np.float64)) + T[b]
    np.add.at(pos, vid, contrib * weights["w"][:, None].astype(np.float64))
    return pos


def skin_surface(surf, bones):
    """(positions (N,3), normals (N,3)); the normal uses the matrix of the vertex's first weight (no translation)."""
    M, T = bones
    pos = skin_positions(surf.wcount, surf.weights, bones)
    first = surf.wstart[:-1]
    nrm = np.einsum("vij,vj->vi", M[surf.weights["b"][first]], surf.normals.astype(np.float64))
    return pos, nrm


# ---------------------------------------------------------------------------------------------- Loop subdivision
@dataclass
class SmoothOpts:
    crease_angle: float = 90.0
    min_weight: float = 0.01
    max_weights: int = 4
    tangential: float = 0.0  # fraction of the Loop tangential displacement kept (0 = normal part only, UVs stay put)
    binding: str = "base"  # skin binding of smoothed verts: "base" (linear point) or "loop" (Loop stencil)
    decal_tris: int = 24  # a shell with <= this many triangles ...
    decal_area: float = 0.05  # ... or an area below this fraction of the largest shell is a decal candidate
    decal_dist: float = 1.5  # ... if all its verts lie within this of a larger shell (0 disables decal handling)


def _flat_weights(lists):
    wc = np.array([len(l) for l in lists], "<i4")
    w = np.empty(int(wc.sum()), WDT)
    w["b"] = [b for l in lists for b, _, _ in l]
    w["w"] = [x for l in lists for _, x, _ in l]
    w["o"] = np.array([o for l in lists for _, _, o in l], np.float64).reshape(-1, 3)
    return wc, w


def _combine(stencil, tl, tkey, opts):
    """Blend topology-vertex weight lists with a sparse stencil: W_b = sum a_i w_ib, O_b = sum a_i w_ib o_ib / W_b.
    Returns (full, pruned): pruned drops W<min_weight, caps the count, renormalises, sorts by weight descending."""
    acc = {}
    for t, a in sorted(stencil.items(), key=lambda x: tkey[x[0]]):  # canonical order: bit-identical in every surface
        for b, w, o in tl[t]:
            aw = a * w
            e = acc.get(b)
            if e is None:
                acc[b] = [aw, aw * o]
            else:
                e[0] += aw
                e[1] = e[1] + aw * o
    full = [(b, e[0], e[1] / e[0]) for b, e in acc.items() if e[0] > 0]
    full.sort(key=lambda x: (-x[1], x[0]))
    return _prune(full, opts)


def _prune(full, opts):
    kept = [x for x in full if x[1] >= opts.min_weight][:opts.max_weights] or full[:1]
    tot = sum(x[1] for x in kept)
    return full, [(b, w / tot, o) for b, w, o in kept]


def _closest_bary(p, A, B, C):
    """Closest point of triangles (A,B,C) (each (K,3)) to point p: returns (dist (K,), bary (K,3))."""
    ab, ac, ap = B - A, C - A, p - A
    d1, d2 = (ab * ap).sum(1), (ac * ap).sum(1)
    bp = p - B
    d3, d4 = (ab * bp).sum(1), (ac * bp).sum(1)
    cp = p - C
    d5, d6 = (ab * cp).sum(1), (ac * cp).sum(1)
    vc, vb, va = d1 * d4 - d3 * d2, d5 * d2 - d1 * d6, d3 * d6 - d5 * d4
    den = va + vb + vc
    bad = np.abs(den) < 1e-18
    den = np.where(bad, 1.0, den)
    v, w = vb / den, vc / den
    bary = np.stack([1 - v - w, v, w], 1)

    def put(mask, b):
        nonlocal bary
        bary = np.where(mask[:, None], b, bary)
    z, o = np.zeros_like(d1), np.ones_like(d1)
    with np.errstate(divide="ignore", invalid="ignore"):
        # Ericson's cases, applied from lowest to highest priority
        e = d4 - d3
        f = d5 - d6
        put((va <= 0) & (e >= 0) & (f >= 0), np.stack([z, 1 - e / (e + f), e / (e + f)], 1))  # edge BC
        put((vb <= 0) & (d2 >= 0) & (d6 <= 0), np.stack([1 - d2 / (d2 - d6), z, d2 / (d2 - d6)], 1))  # edge AC
        put((d6 >= 0) & (d5 <= d6), np.stack([z, z, o], 1))  # vertex C
        put((vc <= 0) & (d1 >= 0) & (d3 <= 0), np.stack([1 - d1 / (d1 - d3), d1 / (d1 - d3), z], 1))  # edge AB
        put((d3 >= 0) & (d4 <= d3), np.stack([z, o, z], 1))  # vertex B
        put((d1 <= 0) & (d2 <= 0), np.stack([o, z, z], 1))  # vertex A
    pt = bary[:, 0:1] * A + bary[:, 1:2] * B + bary[:, 2:3] * C
    dist = np.linalg.norm(pt - p, axis=1)
    dist = np.where(bad | ~np.isfinite(dist), np.inf, dist)
    return dist, bary


def _components(tt, nt_):
    par = list(range(nt_))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for a, b, c in tt:
        for u, v in ((a, b), (b, c)):
            ru, rv = find(int(u)), find(int(v))
            if ru != rv:
                par[ru] = rv
    return np.array([find(x) for x in range(nt_)])


def smooth_surface(s, bones, opts):
    """One Loop level on a skinned surface. Returns (new surface or s, info dict)."""
    n, T = s.numVerts, s.numTris
    info = dict(before_v=n, before_t=T, after_v=n, after_t=T, changed=False, reason="", prune_err=0.0, max_w=int(s.wcount.max()))
    pos0, nrm0 = skin_surface(s, bones)
    ws = s.wstart
    keys = {}
    wel = np.empty(n, np.int64)
    for i in range(n):
        wel[i] = keys.setdefault(s.weights[ws[i]:ws[i + 1]].tobytes(), len(keys))
    nt_ = len(keys)
    rep = np.empty(nt_, np.int64)
    rep[wel[::-1]] = np.arange(n)[::-1]  # first vertex of each topology vertex
    tkey = {t: s.weights[ws[rep[t]]:ws[rep[t] + 1]].tobytes() for t in range(nt_)}
    tl = [[(int(w["b"]), float(w["w"]), w["o"].astype(np.float64)) for w in s.weights[ws[rep[t]]:ws[rep[t] + 1]]] for t in range(nt_)]
    tp = pos0[rep]
    tris = s.triangles
    tt = wel[tris]

    # new (edge) output vertices, unique by (topology edge, uv)
    newv = {}  # key -> [target, length]
    tri_keys = []
    uv = s.uvs
    for k in range(T):
        c = tris[k]
        ks = []
        for p, q in ((c[0], c[1]), (c[1], c[2]), (c[2], c[0])):
            a, b = int(wel[p]), int(wel[q])
            ek = (a, b) if a < b else (b, a)
            # keyed by the two output vertices (not their weld ids): duplicate vertices stay separate, so the
            # collapse target (the lower-index corner) is always a corner of every triangle that uses the vertex
            key = (min(int(p), int(q)), max(int(p), int(q)))
            if key not in newv:
                newv[key] = [int(min(p, q)), float(np.linalg.norm(tp[a] - tp[b])), len(newv), ek,
                             ((uv[p] + uv[q]) * np.float32(0.5)).astype("<f4")]
            ks.append(key)
        tri_keys.append(ks)
    nv_out, nt_out = n + len(newv), 4 * T
    for lim, name, val in ((SHADER_MAX_VERTEXES, "verts>4000", nv_out), (MDS_MAX_VERTS, "verts>6000", nv_out), (MDS_MAX_TRIANGLES, "tris>8192", nt_out)):
        if val > lim:
            info["reason"] = "%s (%d)" % (name, val)
            return s, info
    if nv_out > SHADER_MAX_VERTEXES or nv_out > MDS_MAX_VERTS:
        info["reason"] = "too many verts"
        return s, info

    # welded edges
    edges = {}
    for k in range(T):
        a, b, c = (int(x) for x in tt[k])
        for u, v, o in ((a, b, c), (b, c, a), (c, a, b)):
            if u != v:
                edges.setdefault((u, v) if u < v else (v, u), []).append((k, o, (u, v)))
    fn = np.cross(tp[tt[:, 1]] - tp[tt[:, 0]], tp[tt[:, 2]] - tp[tt[:, 0]])
    ln = np.linalg.norm(fn, axis=1)
    fnu = fn / np.maximum(ln, 1e-12)[:, None]
    cos_c = math.cos(math.radians(opts.crease_angle))
    ecls = {}
    for e, lst in edges.items():
        if len(lst) == 1:
            ecls[e] = "B"
        elif len(lst) > 2:
            ecls[e] = "C"
        else:
            (k1, _, d1), (k2, _, d2) = lst
            same_dir = d1 == d2  # inconsistent winding across the edge: treat as crease
            ecls[e] = "C" if same_dir or (ln[k1] > 1e-9 and ln[k2] > 1e-9 and float(fnu[k1] @ fnu[k2]) < cos_c) else "S"
    nb = [[] for _ in range(nt_)]
    for (a, b), c in ecls.items():
        nb[a].append((b, c)); nb[b].append((a, c))
    vstencil = []  # None = pinned
    nclass = {"pin_boundary": 0, "pin_corner": 0, "crease": 0, "loop": 0}
    for t in range(nt_):
        cl = [x for x in nb[t] if x[1] == "C"]
        if any(c == "B" for _, c in nb[t]) or not nb[t]:
            vstencil.append(None); nclass["pin_boundary"] += 1
        elif len(cl) == 2:
            vstencil.append({t: 0.75, cl[0][0]: 0.125, cl[1][0]: 0.125}); nclass["crease"] += 1
        elif len(cl) != 0 or len(nb[t]) < 3:
            vstencil.append(None); nclass["pin_corner"] += 1
        else:
            m = len(nb[t])
            beta = 3.0 / 16 if m == 3 else 3.0 / (8 * m)
            st = {t: 1 - m * beta}
            for o, _ in nb[t]:
                st[o] = beta
            vstencil.append(st); nclass["loop"] += 1
    info["classes"] = nclass
    info["ecls"] = {c: sum(1 for x in ecls.values() if x == c) for c in "BCS"}

    # ---- normals of the original welded mesh (frame 0), used to project the Loop displacement
    def accum(p, tri, vid, nv, mag=False):
        c = np.cross(p[tri[:, 1]] - p[tri[:, 0]], p[tri[:, 2]] - p[tri[:, 0]])
        if mag:
            c = np.linalg.norm(c, axis=1)
        a = np.zeros((nv, 1 if mag else 3))
        for j in range(3):
            np.add.at(a, vid[tri[:, j]], c[:, None] if mag else c)
        return a
    acc0t = accum(pos0, tris, wel, nt_)
    sign = -1.0 if float((acc0t[wel] * nrm0).sum()) < 0 else 1.0
    mg0 = accum(pos0, tris, wel, nt_, True)[:, 0]
    n0 = np.linalg.norm(acc0t, axis=1)
    fb = nrm0[rep] / np.maximum(np.linalg.norm(nrm0[rep], axis=1), 1e-12)[:, None]
    tn = np.where((n0 > 1e-3 * mg0)[:, None], sign * acc0t / np.maximum(n0, 1e-12)[:, None], fb)

    # ---- odd vertex stencils, ordered
    order = sorted(newv.items(), key=lambda kv: (-kv[1][1], kv[1][2]))
    ost, targets, eidx = [], [], {}
    for r, (key, (tgt, _, _, ek, _)) in enumerate(order):
        (a_, b_) = ek
        smooth_edge = a_ != b_ and ecls[(a_, b_)] == "S"
        if a_ == b_:
            st = {a_: 1.0}
        elif smooth_edge:
            opp = [o for _, o, _ in edges[(a_, b_)]]
            st = {}
            for t_, c_ in ((a_, 0.375), (b_, 0.375), (opp[0], 0.125), (opp[1], 0.125)):
                st[t_] = st.get(t_, 0.0) + c_
        else:
            st = {a_: 0.5, b_: 0.5}
        ost.append((a_, b_, st, smooth_edge)); targets.append(tgt); eidx[key] = n + r
    no = len(ost)

    # ---- base (linear) points, Loop points, normal-projected displacements
    ebase = tp.copy()
    eloop = tp.copy()
    for t in range(nt_):
        if vstencil[t] is not None:
            eloop[t] = sum(a * tp[i] for i, a in vstencil[t].items())
    obase = np.array([(tp[a_] + tp[b_]) * 0.5 for a_, b_, _, _ in ost]).reshape(-1, 3)
    oloop = np.array([sum(a * tp[i] for i, a in st.items()) for _, _, st, _ in ost]).reshape(-1, 3)
    F = opts.tangential

    def project(d, nrm, zero):
        dn = (d * nrm).sum(1, keepdims=True) * nrm
        out = dn + F * (d - dn)
        return np.where(zero[:, None], 0.0, out)
    ezero = np.array([vstencil[t] is None for t in range(nt_)])
    dispE = project(eloop - ebase, tn, ezero)
    on = np.array([tn[a_] + tn[b_] for a_, b_, _, _ in ost]).reshape(-1, 3)
    onl = np.linalg.norm(on, axis=1)
    on = on / np.maximum(onl, 1e-12)[:, None]
    ozero = np.array([not sm for _, _, _, sm in ost], bool) | (onl < 1e-3)
    dispO = project(oloop - obase, on, ozero) if no else np.zeros((0, 3))
    if F != 0 and no:  # degenerate odd normals still get the tangential part when asked for
        dispO = np.where((onl < 1e-3)[:, None] & ~np.array([not sm for _, _, _, sm in ost], bool)[:, None], F * (oloop - obase), dispO)

    # ---- decal shells: small components close to a larger one ride on the larger shell's displacement
    comp = _components(tt, nt_)
    ctri = collections.defaultdict(list)
    for k in range(T):
        if len(set(tt[k])) == 3:
            ctri[comp[tt[k][0]]].append(k)
    carea = {c: float(ln[ks].sum()) * 0.5 for c, ks in ctri.items()}
    cverts = collections.defaultdict(list)
    for t in range(nt_):
        cverts[comp[t]].append(t)
    big = max(carea, key=carea.get) if carea else None
    decal_of = {}  # topo vertex -> (nearest tri corners, bary) filled below
    comps_info = []
    dmap = {}
    if opts.decal_dist > 0 and big is not None:
        for c, ks in sorted(ctri.items(), key=lambda kv: -carea[kv[0]]):
            if c == big or carea[c] >= carea[big]:
                continue
            small = len(ks) <= opts.decal_tris or carea[c] < opts.decal_area * carea[big]
            larger = [x for x in ctri if carea[x] > carea[c]]
            lk = np.array([k for x in larger for k in ctri[x]], np.int64)
            A, B, C_ = tp[tt[lk, 0]], tp[tt[lk, 1]], tp[tt[lk, 2]]
            dists = []
            for t in cverts[c]:
                dd, _ = _closest_bary(tp[t], A, B, C_)
                dists.append(dd.min())
            dmax = float(max(dists)) if dists else float("inf")
            flag = small and dmax <= opts.decal_dist
            ctr = tp[cverts[c]].mean(0)
            comps_info.append(dict(tris=len(ks), area=carea[c], verts=len(cverts[c]), maxdist=dmax, flagged=bool(flag),
                                   center=ctr.round(2).tolist(), small=bool(small)))
            if flag:
                dmap[c] = (A, B, C_, lk)
    info["comps"] = comps_info
    decal_topo = np.zeros(nt_, bool)
    if dmap:
        def ride(p, c):
            A, B, C_, lk = dmap[c]
            dd, bar = _closest_bary(p, A, B, C_)
            i = int(np.argmin(dd))
            cr = tt[lk[i]]
            return bar[i, 0] * dispE[cr[0]] + bar[i, 1] * dispE[cr[1]] + bar[i, 2] * dispE[cr[2]]
        for c in dmap:
            for t in cverts[c]:
                decal_topo[t] = True
                dispE[t] = ride(ebase[t], c)
        for r, (a_, b_, st, sm) in enumerate(ost):
            if decal_topo[a_]:
                dispO[r] = ride(obase[r], comp[a_])
    odecal = np.array([decal_topo[a_] for a_, _, _, _ in ost], bool)
    info["decal_verts"] = int(decal_topo.sum())

    # ---- skin binding + exact frame-0 correction
    M0all = bones[0]

    def finish(stencil, base_stencil_pos, target, use_base, force):
        """Blend weights with `stencil`, then shift every bone offset by M_b^T c so that frame 0 lands on `target`."""
        full, pr = _combine(stencil, tl, tkey, opts)
        c = target - base_stencil_pos
        if not force and float(np.linalg.norm(c)) < 1e-9:
            return full, pr
        def shift(lst):
            return [(b, w_, o + M0all[b].T @ c) for b, w_, o in lst]
        f2 = shift(full)
        f3, p3 = _prune(f2, opts)
        return f2, p3
    even_full, even_lists = [], []
    for t in range(nt_):
        target = ebase[t] + dispE[t]
        use_loop = opts.binding == "loop" and not decal_topo[t]
        if use_loop and vstencil[t] is not None:
            f, p = finish(vstencil[t], eloop[t], target, False, False)
        elif np.linalg.norm(dispE[t]) < 1e-12 and not decal_topo[t]:
            f, p = tl[t], tl[t]
        else:
            f, p = finish({t: 1.0}, ebase[t], target, True, True)
        even_full.append(f); even_lists.append(p)
    odd_full, odd_lists = [], []
    for r, (a_, b_, st, sm) in enumerate(ost):
        target = obase[r] + dispO[r]
        if opts.binding == "loop" and not odecal[r]:
            f, p = finish(st, oloop[r], target, False, False)
        elif np.linalg.norm(dispO[r]) < 1e-12 and not odecal[r]:
            f, p = _combine({a_: 0.5, b_: 0.5} if a_ != b_ else {a_: 1.0}, tl, tkey, opts)
        else:
            f, p = finish({a_: 0.5, b_: 0.5} if a_ != b_ else {a_: 1.0}, obase[r], target, True, True)
        odd_full.append(f); odd_lists.append(p)

    out_lists = [even_lists[wel[i]] for i in range(n)] + odd_lists
    full_lists = [even_full[wel[i]] for i in range(n)] + odd_full
    wc, w = _flat_weights(out_lists)
    wcf, wf = _flat_weights(full_lists)
    pos_p = skin_positions(wc, w, bones)
    pos_f = skin_positions(wcf, wf, bones)
    tgt_all = np.concatenate([(ebase + dispE)[wel], obase + dispO]) if no else (ebase + dispE)[wel]
    info["prune_err"] = float(np.abs(pos_p - pos_f).max())
    info["frame0_err"] = float(np.abs(pos_f - tgt_all).max())
    info["dbg"] = dict(wel=wel, rep=rep, nt=nt_, vstencil=vstencil, ost=ost, decal_topo=decal_topo, odecal=odecal, tris=tris, tt=tt,
                       sign=sign, ezero=ezero, ozero=ozero)

    # triangles: 4 children, original winding
    ot = np.empty((T * 4, 3), "<i4")
    for k in range(T):
        c0, c1, c2 = (int(x) for x in tris[k])
        m01, m12, m20 = (eidx[key] for key in tri_keys[k])
        ot[4 * k:4 * k + 4] = ((c0, m01, m20), (c1, m12, m01), (c2, m20, m12), (m01, m12, m20))

    # normals: area-weighted over output verts welded by weight list (sign calibrated against the original mesh)
    ok = {}
    wso = np.concatenate([[0], np.cumsum(wc)]).astype(np.int64)
    ovid = np.array([ok.setdefault(w[wso[i]:wso[i + 1]].tobytes(), len(ok)) for i in range(nv_out)])
    acc = accum(pos_p, ot, ovid, len(ok))[ovid] * sign
    fallback = np.concatenate([nrm0, nrm0[np.array(targets, np.int64)]]) if len(targets) else nrm0
    nl = np.linalg.norm(acc, axis=1)
    mg = accum(pos_p, ot, ovid, len(ok), True)[ovid][:, 0]
    nl = np.where(nl > 1e-3 * mg, nl, 0.0)  # double-sided cloth: opposite faces cancel, keep the original normal
    nw = np.where(nl[:, None] > 1e-12, acc / np.maximum(nl, 1e-12)[:, None], fallback)
    M0 = bones[0][w["b"][np.concatenate([[0], np.cumsum(wc)[:-1]])]]
    nloc = np.einsum("vji,vj->vi", M0, nw)  # inverse of skin_surface: M^T n

    tg = np.array(targets, np.int64)
    out = MDSSurface(
        s.ident, s.name_raw, s.shader_raw, s.shaderIndex, s.minLod,
        nloc.astype("<f4"),
        np.concatenate([s.uvs, np.array([v[4] for _, v in order], "<f4").reshape(-1, 2)]),
        np.concatenate([s.fixedParent, s.fixedParent[tg]]).astype("<i4"),
        np.concatenate([s.fixedDist, s.fixedDist[tg]]).astype("<f4"),
        wc, w, ot, np.concatenate([s.collapseMap, tg]).astype("<i4"), s.boneRefs.copy())
    info.update(changed=True, after_v=nv_out, after_t=nt_out, max_w=int(wc.max()))
    return out, info


def smooth_model(m, opts):
    bones = pose_frame(m, 0)
    new = []
    infos = []
    for s in m.surfaces:
        o, i = smooth_surface(s, bones, opts)
        new.append(o); infos.append(i)
    return replace(m, lods=[new]), infos


# ---------------------------------------------------------------------------------------------- pak access
def load_mds_files(pattern=None):
    out = {}
    for pak in PAKS:
        with zipfile.ZipFile(pak) as z:
            for n in sorted(z.namelist()):
                if n.lower().endswith(".mds") and (not pattern or fnmatch.fnmatch(n.lower(), "*" + pattern.lower() + "*")
                                                   or fnmatch.fnmatch(n.lower(), pattern.lower())):
                    out[n] = z.read(n)
    return out


# ---------------------------------------------------------------------------------------------- stats
def surface_stats(s):
    keys = {}
    wel = np.empty(s.numVerts, np.int64)
    ws = s.wstart
    for i in range(s.numVerts):
        k = s.weights[ws[i]:ws[i + 1]].tobytes()
        wel[i] = keys.setdefault(k, len(keys))
    edges = {}
    for t in wel[s.triangles]:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            if a == b:
                continue
            e = (a, b) if a < b else (b, a)
            edges[e] = edges.get(e, 0) + 1
    ue = set()
    for t in s.triangles:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            ue.add((a, b) if a < b else (b, a))
    boundary = sum(1 for c in edges.values() if c == 1)
    nonman = sum(1 for c in edges.values() if c > 2)
    pv = s.numVerts + len(ue)
    pt = s.numTris * 4
    return dict(welded=len(keys), boundary=boundary, nonman=nonman, pv=pv, pt=pt, uedges=len(ue),
                fit=(pv <= SHADER_MAX_VERTEXES and pv <= MDS_MAX_VERTS and pt <= MDS_MAX_TRIANGLES),
                flags=[f for f, c in (("VERTS>4000", pv > SHADER_MAX_VERTEXES), ("VERTS>6000", pv > MDS_MAX_VERTS),
                                      ("TRIS>8192", pt > MDS_MAX_TRIANGLES)) if c])


def cmd_stats(pattern):
    files = load_mds_files(pattern)
    fit = nofit = 0
    for n, d in files.items():
        m = parse_mds(d)
        print("%s: numLODs=1 (v4 has no LOD table) numFrames=%d numBones=%d numTags=%d numSurfaces=%d"
              % (n, m.numFrames, m.numBones, m.numTags, len(m.surfaces)))
        for s in m.surfaces:
            st = surface_stats(s)
            mw = s.wcount.max() if s.numVerts else 0
            av = s.wcount.mean() if s.numVerts else 0
            print("  %-14s %-44s V=%5d T=%5d w(max/mean)=%d/%.2f boneRefs=%2d minLod=%4d welded=%5d bnd=%3d nonman=%3d -> V=%5d T=%5d %s"
                  % (s.name, s.shader, s.numVerts, s.numTris, mw, av, len(s.boneRefs), s.minLod, st["welded"], st["boundary"],
                     st["nonman"], st["pv"], st["pt"], "FIT" if st["fit"] else "NOFIT " + ",".join(st["flags"])))
            if st["fit"]:
                fit += 1
            else:
                nofit += 1
    print("\nSUMMARY: %d surfaces in %d models after 1 Loop level: %d fit, %d do not fit" % (fit + nofit, len(files), fit, nofit))


def cmd_roundtrip():
    ok = 0
    files = load_mds_files()
    for n, d in files.items():
        try:
            out = write_mds(parse_mds(d))
            same = out == d
            if not same:
                diff = next((i for i in range(min(len(out), len(d))) if out[i] != d[i]), min(len(out), len(d)))
                msg = "DIFF at byte %d (len %d vs %d)" % (diff, len(out), len(d))
        except Exception as e:
            same, msg = False, "ERROR %s" % e
        print("%s %s" % ("OK  " if same else "DIFF", n) + ("" if same else "  " + msg))
        ok += same
    print("%d/%d byte-identical" % (ok, len(files)))
    return ok == len(files)


# ---------------------------------------------------------------------------------------------- OBJ
def cmd_obj(path, out, frame, lod, opts=None):
    if lod != 0:
        sys.exit("MDS v4 has a single surface list: --lod must be 0")
    files = load_mds_files(path)
    key = [n for n in files if n.lower() == path.lower()]
    if not key:
        sys.exit("model not found in paks: " + path)
    m = parse_mds(files[key[0]])
    if opts is not None:
        m, _ = smooth_model(m, opts)
    bones = pose_frame(m, frame)
    lines = ["# %s frame %d (derived from RTCW assets: do not redistribute)" % (key[0], frame)]
    base = 1
    swap_votes = [0, 0]
    allpos = []
    for s in m.surfaces:
        pos, nrm = skin_surface(s, bones)
        allpos.append(pos)
        t = s.triangles
        fn = np.cross(pos[t[:, 1]] - pos[t[:, 0]], pos[t[:, 2]] - pos[t[:, 0]])
        d = np.einsum("ti,ti->t", fn, nrm[t].sum(axis=1))
        swap_votes[0] += int((d > 0).sum()); swap_votes[1] += int((d < 0).sum())
    # RTCW indices are clockwise seen from outside; OBJ wants counter-clockwise. Verify by comparing with skinned normals.
    flip = swap_votes[1] > swap_votes[0]
    print("winding: %d faces agree with normals as stored, %d disagree -> %s" %
          (swap_votes[0], swap_votes[1], "reversing (a,c,b)" if flip else "keeping (a,b,c)"), file=sys.stderr)
    for s in m.surfaces:
        pos, nrm = skin_surface(s, bones)
        lines.append("o %s" % (s.name or "surface"))
        lines.append("g %s" % (s.name or "surface"))
        lines.append("# shader %s" % s.shader)
        lines += ["v %.5f %.5f %.5f" % tuple(p) for p in pos]
        lines += ["vt %.6f %.6f" % (u, 1.0 - v) for u, v in s.uvs]
        lines += ["vn %.5f %.5f %.5f" % tuple(n) for n in nrm]
        for a, b, c in s.triangles + base:
            if flip:
                b, c = c, b
            lines.append("f %d/%d/%d %d/%d/%d %d/%d/%d" % (a, a, a, b, b, b, c, c, c))
        base += s.numVerts
    Path(out).write_text("\n".join(lines) + "\n")
    allp = np.concatenate(allpos)
    print("wrote %s: %d surfaces, bbox min %s max %s" % (out, len(m.surfaces), allp.min(0).round(2), allp.max(0).round(2)))


def _jacobians(pos, uv, tri):
    """Affine maps UV -> 3D per triangle (T,3,2) and a validity mask."""
    e = np.stack([pos[tri[:, 1]] - pos[tri[:, 0]], pos[tri[:, 2]] - pos[tri[:, 0]]], 2)  # (T,3,2)
    u = np.stack([uv[tri[:, 1]] - uv[tri[:, 0]], uv[tri[:, 2]] - uv[tri[:, 0]]], 2).astype(np.float64)  # (T,2,2)
    det = u[:, 0, 0] * u[:, 1, 1] - u[:, 0, 1] * u[:, 1, 0]
    ok = np.abs(det) > 1e-12
    ui = np.linalg.inv(np.where(ok[:, None, None], u, np.eye(2)))
    return e @ ui, ok


def distortion(s0, s1, bones):
    """Texture distortion of every child triangle vs its parent (frame 0): relative Jacobian change and
    anisotropy (singular value ratio) change, as per-triangle arrays."""
    p0, _ = skin_surface(s0, bones)
    p1, _ = skin_surface(s1, bones)
    jp, okp = _jacobians(p0, s0.uvs, s0.triangles)
    jc, okc = _jacobians(p1, s1.uvs, s1.triangles)
    jp4 = np.repeat(jp, 4, axis=0)
    ok = np.repeat(okp, 4) & okc
    rel = np.linalg.norm(jc - jp4, axis=(1, 2)) / np.maximum(np.linalg.norm(jp4, axis=(1, 2)), 1e-12)
    sp = np.linalg.svd(jp4, compute_uv=False)
    sc = np.linalg.svd(jc, compute_uv=False)
    ap = sp[:, 0] / np.maximum(sp[:, 1], 1e-9)
    ac = sc[:, 0] / np.maximum(sc[:, 1], 1e-9)
    aniso = np.maximum(ac / ap, ap / ac)
    return rel[ok], aniso[ok]


def cmd_distortion(pattern, opts):
    for n, d in load_mds_files(pattern).items():
        m0 = parse_mds(d)
        m1, infos = smooth_model(m0, opts)
        B = pose_frame(m0, 0)
        print(n)
        R, A = [], []
        for s0, s1, inf in zip(m0.surfaces, m1.surfaces, infos):
            if not inf["changed"]:
                continue
            r, a = distortion(s0, s1, B)
            R.append(r); A.append(a)
            print("  %-12s jacobian change mean %.3f max %.3f | stretch ratio mean %.2f max %.2f | decal verts %d"
                  % (s0.name, r.mean(), r.max(), a.mean(), a.max(), inf["decal_verts"]))
        R, A = np.concatenate(R), np.concatenate(A)
        print("  ALL          jacobian change mean %.3f max %.3f | stretch ratio mean %.2f max %.2f" % (R.mean(), R.max(), A.mean(), A.max()))


def cmd_smooth(pattern, opts, pk3):
    import time
    t0 = time.time()
    files = load_mds_files(pattern)
    if not files:
        sys.exit("no MDS matches " + str(pattern))
    tv0 = tv1 = nkept = nsurf = 0
    perr = 0.0
    Path(pk3).parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pk3, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in files.items():
            m, infos = smooth_model(parse_mds(d), opts)
            z.writestr(n, write_mds(m))
            b = sum(i["before_v"] for i in infos); a = sum(i["after_v"] for i in infos)
            tv0 += b; tv1 += a
            for s, i in zip(m.surfaces, infos):
                nsurf += 1
                perr = max(perr, i["prune_err"])
                if not i["changed"]:
                    nkept += 1
                    print("  KEPT %s %s: %s" % (n, s.name, i["reason"]))
            print("%s: verts %d -> %d, tris %d -> %d, max weights %d, prune err %.2e, frame-0 binding err %.1e, decal verts %d"
                  % (n, b, a, sum(i["before_t"] for i in infos), sum(i["after_t"] for i in infos),
                     max(i["max_w"] for i in infos), max(i["prune_err"] for i in infos),
                     max(i.get("frame0_err", 0) for i in infos), sum(i.get("decal_verts", 0) for i in infos)))
    print("%d models, %d surfaces (%d kept unchanged); verts %d -> %d (x%.2f); max pruning error %.2e units; %.1f s; wrote %s"
          % (len(files), nsurf, nkept, tv0, tv1, tv1 / max(tv0, 1), perr, time.time() - t0, pk3))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stats", nargs="?", const="", metavar="GLOB", help="per-surface stats and Loop-subdivision projection")
    ap.add_argument("--roundtrip", action="store_true", help="parse+write every MDS and compare bytes")
    ap.add_argument("--obj", metavar="MODEL_PATH", help="dump a skinned pose as OBJ")
    ap.add_argument("--out", metavar="FILE.obj")
    ap.add_argument("--frame", type=int, default=0)
    ap.add_argument("--smooth", metavar="GLOB", help="one Loop level on matching models, written to --pk3")
    ap.add_argument("--smoothed", action="store_true", help="with --obj: dump the smoothed model")
    ap.add_argument("--pk3", default=str(ROOT / "run/codmod/codmod_smooth.pk3"), help="output pk3 for --smooth")
    ap.add_argument("--distortion", nargs="?", const="", metavar="GLOB", help="texture distortion report of the smoothing (frame 0)")
    ap.add_argument("--tangential", type=float, default=0.0, help="fraction of the Loop tangential displacement to keep (default 0: normal part only)")
    ap.add_argument("--binding", choices=("base", "loop"), default="base", help="skin binding of smoothed vertices")
    ap.add_argument("--decal-tris", type=int, default=24, help="shells with at most this many triangles are decal candidates")
    ap.add_argument("--decal-area", type=float, default=0.05, help="... or with area below this fraction of the largest shell")
    ap.add_argument("--decal-dist", type=float, default=1.5, help="... if within this distance of a larger shell (0 disables)")
    ap.add_argument("--crease-angle", type=float, default=90.0, help="dihedral angle (deg, frame 0) above which an edge is a crease")
    ap.add_argument("--min-weight", type=float, default=0.01, help="drop smoothed bone weights below this")
    ap.add_argument("--max-weights", type=int, default=4, help="max weights per smoothed vertex")
    ap.add_argument("--lod", type=int, default=0, help="only 0 (v4 MDS has no LOD table)")
    a = ap.parse_args()
    if a.roundtrip:
        sys.exit(0 if cmd_roundtrip() else 1)
    opts = SmoothOpts(a.crease_angle, a.min_weight, a.max_weights, a.tangential, a.binding, a.decal_tris, a.decal_area, a.decal_dist)
    if a.smooth is not None:
        cmd_smooth(a.smooth, opts, a.pk3)
    elif a.distortion is not None:
        cmd_distortion(a.distortion or None, opts)
    elif a.stats is not None:
        cmd_stats(a.stats or None)
    elif a.obj:
        if not a.out:
            ap.error("--obj needs --out")
        cmd_obj(a.obj, a.out, a.frame, a.lod, opts if a.smoothed else None)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
