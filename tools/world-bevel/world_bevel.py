#!/usr/bin/env python3
"""RTCW SP world-bevel prototype: round the sharp convex wall corners of a BSP, visual only.

Reads the owned game paks in run/main/ and writes a private override pack (maps/NAME.bsp only). The output is derived
from proprietary assets: git-ignored, never commit or redistribute.

  python3 -I tools/world-bevel/world_bevel.py --roundtrip [--all]
  python3 -I tools/world-bevel/world_bevel.py --map escape1 --stats
  python3 -I tools/world-bevel/world_bevel.py --map escape1 --validate
  python3 -I tools/world-bevel/world_bevel.py --map escape1 --obj /tmp/c.obj --region x0 y0 z0 x1 y1 z1
  python3 -I tools/world-bevel/world_bevel.py --map escape1 --pk3 run/codmod/codmod_bevel.pk3 [--radius 3 ...]

Only lumps 10 (drawverts), 11 (drawindexes) and 13 (surfaces) are rewritten; every other lump is copied verbatim (the
collision data is untouched: the bevel is visual only). Surface count and order never change. Offsets are recomputed
(4-byte aligned, the stock layout is reproduced byte for byte by --roundtrip).

Algorithm (world model faces only; see README.md): boundary edges of every candidate planar face are matched by
collinear overlap (so T-junctions do not matter), kept when convex with a dihedral (angle between the two face normals)
inside [--min-angle, --max-angle], then every face is clipped back by --radius along the edge (tapering linearly to
zero over --taper units at both ends of the shared interval) and a circular-arc strip is added. Strip triangles are
appended to the surface of the face they derive from. See --surface-type for how the engine sees those surfaces.
"""
import argparse, collections, glob, math, os, re, struct, sys, zipfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PAK_GLOB = str(ROOT / "run/main/*.pk3")
DEFAULT_PK3 = ROOT / "run/codmod/codmod_bevel.pk3"

IDENT, VERSION, NLUMPS = b"IBSP", 47, 17
HEADER_SIZE = 8 + NLUMPS * 8
L_ENT, L_SHADER, L_PLANE, L_NODE, L_LEAF, L_LSURF, L_LBRUSH, L_MODEL, L_BRUSH, L_BSIDE, L_VERT, L_INDEX, L_FOG, \
    L_SURF, L_LM, L_GRID, L_VIS = range(17)

DRAWVERT = np.dtype([("xyz", "<f4", 3), ("st", "<f4", 2), ("lm", "<f4", 2), ("n", "<f4", 3), ("c", "u1", 4)])
SURFACE = np.dtype([("shader", "<i4"), ("fog", "<i4"), ("type", "<i4"), ("fv", "<i4"), ("nv", "<i4"), ("fi", "<i4"),
                    ("ni", "<i4"), ("lmn", "<i4"), ("lmx", "<i4"), ("lmy", "<i4"), ("lmw", "<i4"), ("lmh", "<i4"),
                    ("org", "<f4", 3), ("vecs", "<f4", (3, 3)), ("pw", "<i4"), ("ph", "<i4")])
SHADER = np.dtype([("name", "S64"), ("sf", "<i4"), ("cf", "<i4")])
MODEL = np.dtype([("mins", "<f4", 3), ("maxs", "<f4", 3), ("fs", "<i4"), ("ns", "<i4"), ("fb", "<i4"), ("nb", "<i4")])
assert DRAWVERT.itemsize == 44 and SURFACE.itemsize == 104 and SHADER.itemsize == 72 and MODEL.itemsize == 40

MST_PLANAR, MST_PATCH, MST_TRISOUP, MST_FLARE = 1, 2, 3, 4
SURF_SKY, SURF_NODRAW, SURF_ALPHASHADOW = 0x4, 0x80, 0x10000
CONTENTS_WATER, CONTENTS_SLIME, CONTENTS_LAVA, CONTENTS_FOG, CONTENTS_TRANSLUCENT = 0x20, 0x10, 0x8, 0x40, 0x20000000
MAX_BEVEL_FACE_VERTS = 1024  # engine BSP_MAX_FACE_VERTS (tr_local.h); a type-1 face above it is reverted
DEFAULT_SKIP = (r"sky|caulk|nodraw|clip|trigger|hint|fog|water|glass|decal|slime|lava|portal|skip|origin|window|"
                r"alpha/|/sfx/|lights?/|_light|flare|cloth|curtain|lightgrid")
NATT = 14  # xyz(3) st(2) lm(2) n(3) color(4)
EPS = 1e-9


# ------------------------------------------------------------------------------------------------ BSP container
def find_bsp(name):
    """Bytes of maps/NAME.bsp from run/main/*.pk3 (sorted by name; the later pak overrides the earlier)."""
    rel, data = f"maps/{name}.bsp", None
    for p in sorted(glob.glob(PAK_GLOB)):
        with zipfile.ZipFile(p) as z:
            if rel in z.namelist():
                data = z.read(rel)
    if data is None:
        sys.exit(f"maps/{name}.bsp not found in {PAK_GLOB}")
    return data


def all_maps():
    names = set()
    for p in glob.glob(PAK_GLOB):
        with zipfile.ZipFile(p) as z:
            names.update(n[5:-4] for n in z.namelist() if n.startswith("maps/") and n.endswith(".bsp") and "/" not in n[5:])
    return sorted(names)


class Bsp:
    def __init__(self, data):
        ident, ver = struct.unpack_from("<4si", data)
        if ident != IDENT or ver != VERSION:
            raise ValueError(f"not an RTCW IBSP v47 file ({ident!r} {ver})")
        self.table = [struct.unpack_from("<ii", data, 8 + 8 * i) for i in range(NLUMPS)]
        self.lumps = [bytes(data[o:o + l]) for o, l in self.table]
        self.order = sorted(range(NLUMPS), key=lambda i: (self.table[i][0], self.table[i][1]))  # on-disk order is kept
        # the (normally zero) alignment bytes after each lump are kept too, so odd paks still roundtrip
        self.pad = {}
        for k, i in enumerate(self.order):
            end = self.table[i][0] + self.table[i][1]
            nxt = self.table[self.order[k + 1]][0] if k + 1 < NLUMPS else len(data)
            self.pad[i] = bytes(data[end:nxt]) if 0 <= nxt - end < 4 else b""

    def write(self):
        out, table = bytearray(HEADER_SIZE), [None] * NLUMPS
        for i in self.order:
            table[i] = (len(out), len(self.lumps[i]))
            out += self.lumps[i]
            need = -len(out) % 4
            out += (self.pad[i] + bytes(4))[:need] if self.pad[i] else bytes(need)
        struct.pack_into("<4si", out, 0, IDENT, VERSION)
        for i, (o, l) in enumerate(table):
            struct.pack_into("<ii", out, 8 + 8 * i, o, l)
        return bytes(out)

    def arr(self, i, dt):
        return np.frombuffer(self.lumps[i], dtype=dt)

    @property
    def verts(self):
        return self.arr(L_VERT, DRAWVERT)

    @property
    def indexes(self):
        return self.arr(L_INDEX, "<i4")

    @property
    def surfaces(self):
        return self.arr(L_SURF, SURFACE)

    @property
    def shaders(self):
        return self.arr(L_SHADER, SHADER)

    @property
    def models(self):
        return self.arr(L_MODEL, MODEL)

    def shader_names(self):
        return [_cstr(x) for x in self.shaders["name"]]

    def entities(self):
        txt = self.lumps[L_ENT].split(b"\0", 1)[0].decode("latin-1")
        return [dict(re.findall(r'"([^"]*)"\s*"([^"]*)"', blk)) for blk in re.findall(r"\{([^}]*)\}", txt)]

    def player_start(self):
        for e in self.entities():
            if e.get("classname") == "info_player_start" and "origin" in e:
                return tuple(float(x) for x in e["origin"].split())
        return None


def _cstr(b):
    return bytes(b).split(b"\0", 1)[0].decode("latin-1")


def cmd_roundtrip(all_):
    names = all_maps() if all_ else ["escape1"]
    bad = 0
    for n in names:
        data = find_bsp(n)
        try:
            ok = Bsp(data).write() == data
        except ValueError as e:
            print(f"  {n}: SKIP ({e})")
            continue
        bad += not ok
        print(f"  {n}: {'identical' if ok else 'MISMATCH'} ({len(data)} bytes)")
    print(f"roundtrip: {len(names) - bad}/{len(names)} byte-identical")
    return bad == 0


# ------------------------------------------------------------------------------------------------ small geometry
def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def poly_area2(P):
    """Twice the area (as the norm of the summed cross products) of a polygon given by its xyz rows."""
    x = P[:, :3]
    c = np.cross(x[1:-1] - x[0], x[2:] - x[0])
    return float(np.linalg.norm(c.sum(0))) if len(c) else 0.0


def mk_poly(pts):
    """List of attribute rows -> (k,NATT) polygon without duplicate consecutive points, or None if degenerate."""
    out = []
    for p in pts:
        if out and np.abs(out[-1][:3] - p[:3]).max() < 1e-7:
            continue
        out.append(p)
    if len(out) > 1 and np.abs(out[0][:3] - out[-1][:3]).max() < 1e-7:
        out.pop()
    if len(out) < 3:
        return None
    P = np.array(out)
    return P if poly_area2(P) > 1e-7 else None


def _interp(a, b, da, db):
    """Crossing of edge a-b where the signed distance changes sign. Endpoints are ordered canonically so two
    polygons sharing the edge compute bitwise identical points."""
    if tuple(a[:3]) > tuple(b[:3]):
        a, b, da, db = b, a, db, da
    return a + (da / (da - db)) * (b - a)


def split_plane(P, sd):
    """Split polygon by signed distances per vertex. Returns (positive part, negative part), either may be None."""
    sd = np.where(np.abs(sd) < EPS, 0.0, sd)
    if sd.min() >= 0:
        return P, None
    if sd.max() <= 0:
        return None, P
    pos, neg, k = [], [], len(P)
    for i in range(k):
        j = (i + 1) % k
        da, db = sd[i], sd[j]
        if da >= 0:
            pos.append(P[i])
        if da <= 0:
            neg.append(P[i])
        if da * db < 0:
            x = _interp(P[i], P[j], da, db)
            pos.append(x)
            neg.append(x)
    return mk_poly(pos), mk_poly(neg)


def triangulate(P):
    """Fan triangulation of a convex polygon (possibly with collinear points); tries apexes until none is degenerate."""
    k = len(P)
    if k == 3:
        return [P]
    for a in range(k):
        tris = []
        for i in range(1, k - 1):
            t = np.array([P[a], P[(a + i) % k], P[(a + i + 1) % k]])
            if poly_area2(t) > 1e-7:
                tris.append(t)
        if len(tris) == k - 2 or (a == k - 1 and tris):
            return tris
    return [np.array([P[0], P[i], P[i + 1]]) for i in range(1, k - 1) if poly_area2(np.array([P[0], P[i], P[i + 1]])) > 1e-7]


def merge_convex(polys, nrm):
    """Greedily join the pieces a clipped face was cut into wherever two pieces share a whole edge and their union stays
    convex (Hertel-Mehlhorn). Fewer, bigger polygons triangulate into far fewer triangles; no vertex is ever removed."""
    key = lambda q: tuple(np.round(q[:3] * 1e4).astype(np.int64))
    items = [([key(q) for q in P], P) for P in polys]
    items = [it for it in items if len(set(it[0])) == len(it[0])]
    dropped = len(polys) - len(items)
    out = []
    changed = True
    while changed:
        changed = False
        edge = {}
        for i, (ks, _P) in enumerate(items):
            for k in range(len(ks)):
                edge[(ks[k], ks[(k + 1) % len(ks)])] = (i, k)
        for i, (ks, P) in enumerate(items):
            if items[i] is None:
                continue
            for k in range(len(ks)):
                a_, b_ = ks[k], ks[(k + 1) % len(ks)]
                hit = edge.get((b_, a_))
                if hit is None or hit[0] == i or items[hit[0]] is None:
                    continue
                j, kj = hit
                kj_, Pj = items[j]
                ki = len(ks)
                # [b ... a] of i, then j after the shared edge up to before b
                rot_i = [(k + 1 + m) % ki for m in range(ki)]
                rot_j = [(kj + 2 + m) % len(kj_) for m in range(len(kj_) - 2)]
                nk = [ks[m] for m in rot_i] + [kj_[m] for m in rot_j]
                nP = np.array([P[m] for m in rot_i] + [Pj[m] for m in rot_j])
                if len(set(nk)) != len(nk):
                    continue
                X = nP[:, :3]
                e1 = np.roll(X, -1, axis=0) - X
                e2 = np.roll(e1, -1, axis=0)
                cr = np.cross(e1, e2) @ nrm
                if (cr < -1e-6 * np.maximum(np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1), 1e-9)).any():
                    continue
                items[i] = (nk, nP)
                items[j] = None
                changed = True
                break
            if changed:
                break
        items = [it for it in items if it is not None]
    return [P for _k, P in items] + ([] if not dropped else [P for P in polys if len(set(key(q) for q in P)) != len(P)])


def slerp(a, b, f, theta):
    return (math.sin((1 - f) * theta) * a + math.sin(f * theta) * b) / math.sin(theta)


# ------------------------------------------------------------------------------------------------ bevel pipeline
class Face:
    """A candidate planar surface: its geometry as float64 attribute rows plus the plane/mapping fits."""

    def __init__(self, bsp, si, surf, shader_name):
        self.si = si
        v = bsp.verts[surf["fv"]:surf["fv"] + surf["nv"]]
        ix = bsp.indexes[surf["fi"]:surf["fi"] + surf["ni"]].reshape(-1, 3)
        self.A = np.concatenate([v["xyz"], v["st"], v["lm"], v["n"], v["c"]], axis=1).astype(np.float64)
        self.tris = ix
        self.n = unit(surf["vecs"][2].astype(np.float64))
        self.d = float((self.A[:, :3] @ self.n).mean())
        self.planar_err = float(np.abs(self.A[:, :3] @ self.n - self.d).max())
        self.surf = surf
        self.name = shader_name
        self.has_lm = surf["lmn"] >= 0
        self.centroid = self.A[:, :3].mean(0)
        # triangle winding relative to the plane normal (+1: (b-a)x(c-a) agrees with n)
        T = self.A[ix, :3]
        g = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]) @ self.n
        big = np.abs(g) > 1e-6
        self.winding = 0
        if big.any():
            self.winding = 1 if (g[big] > 0).all() else (-1 if (g[big] < 0).all() else 0)
        # affine fit (u,v basis of the plane -> st / lightmap)
        a = np.abs(self.n)
        h = np.zeros(3)
        h[int(a.argmin())] = 1.0
        self.u = unit(np.cross(self.n, h))
        self.v = np.cross(self.n, self.u)
        M = np.stack([self.A[:, :3] @ self.u, self.A[:, :3] @ self.v, np.ones(len(self.A))], axis=1)
        self.M = M
        self.fit, _res, _rk, _sv = np.linalg.lstsq(M, self.A[:, 3:7], rcond=None)
        r = M @ self.fit - self.A[:, 3:7]
        self.fit_err_st = float(np.abs(r[:, :2]).max())
        self.fit_err_lm = float(np.abs(r[:, 2:]).max())
        if self.has_lm:
            s = surf
            self.lm_lo = np.array([s["lmx"], s["lmy"]], dtype=np.float64) / 128.0
            self.lm_hi = np.array([s["lmx"] + s["lmw"], s["lmy"] + s["lmh"]], dtype=np.float64) / 128.0
        self.polys = None  # list of (k,NATT) polygons once clipped
        self.strip = []  # strip triangles (3,NATT)
        self.cutverts = []  # (group id, t, position) of vertices on the cut line

    def eval_map(self, x):
        """st, lm for a point x (projected to the plane by the basis), clamped to the lightmap rect."""
        m = np.array([x @ self.u, x @ self.v, 1.0]) @ self.fit
        lm = m[2:]
        if self.has_lm:
            lm = np.minimum(np.maximum(lm, self.lm_lo), self.lm_hi)
        return m[:2], lm

    def nearest_color(self, x):
        return self.A[int(((self.A[:, :3] - x) ** 2).sum(1).argmin()), 10:14]

    def ensure_polys(self):
        if self.polys is None:
            self.polys = [self.A[t] for t in self.tris]


class Group:
    """One bevel run: two planes sharing a line, over the interval [t0,t1] (t = (x-P0).d)."""
    pass


def line_frame(nA, dA, nB, dB):
    d = unit(np.cross(nA, nB))
    M = np.array([nA, nB, d])
    P0 = np.linalg.solve(M, np.array([dA, dB, 0.0]))
    return d, P0


class Bevel:
    def __init__(self, bsp, a):
        self.bsp, self.a = bsp, a
        self.stats = collections.Counter()
        self.skip_re = re.compile(a.skip_shader, re.I) if a.skip_shader else None
        self.faces = {}  # surface index -> Face
        self.groups = []
        self.cap_edges = []  # wall-end edges that lie on the boundary of / inside a wall face: cap edges E -> arc end and under-wall end rows (validation)
        self.tagged = []  # (surface index, kind 'cut'|'strip', tri(3,NATT)) in generation order for validation

    # --- 1. candidates
    def candidates(self):
        bsp, S = self.bsp, self.bsp.surfaces
        names = bsp.shader_names()
        sh = bsp.shaders
        m0 = bsp.models[0]
        for si in range(int(m0["fs"]), int(m0["fs"] + m0["ns"])):
            s = S[si]
            if s["type"] != MST_PLANAR:
                self.stats["surf_not_planar"] += 1
                continue
            nm = names[s["shader"]]
            sf, cf = int(sh["sf"][s["shader"]]), int(sh["cf"][s["shader"]])
            if sf & (SURF_SKY | SURF_NODRAW | SURF_ALPHASHADOW) or cf & (CONTENTS_WATER | CONTENTS_SLIME | CONTENTS_LAVA | CONTENTS_FOG | CONTENTS_TRANSLUCENT) \
                    or (self.skip_re and self.skip_re.search(nm)) or s["fog"] > 0 or s["ni"] < 3:
                self.stats["surf_skipped_shader"] += 1
                continue
            f = Face(bsp, si, s, nm)
            if f.planar_err > 0.1 or f.winding == 0 or f.fit_err_st > 2e-3 or (f.has_lm and f.fit_err_lm > 5e-4):
                self.stats["surf_skipped_bad_face"] += 1
                f.bad = True
            else:
                f.bad = False
            self.faces[si] = f
        self.stats["surf_candidates"] = len(self.faces)

    # --- 2. boundary edges
    def boundary_edges(self):
        P0, P1, F, IN = [], [], [], []
        for si, f in self.faces.items():
            if f.bad:
                continue
            key = np.round(f.A[:, :3] * 64).astype(np.int64)
            _u, wid = np.unique(key, axis=0, return_inverse=True)
            wid = wid.reshape(-1)
            t = wid[f.tris]
            e = np.stack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]], axis=1).reshape(-1, 2)  # (3T,2)
            third = np.stack([f.tris[:, 2], f.tris[:, 0], f.tris[:, 1]], axis=1).reshape(-1)
            ei = np.stack([f.tris[:, [0, 1]], f.tris[:, [1, 2]], f.tris[:, [2, 0]]], axis=1).reshape(-1, 2)
            ok = e[:, 0] != e[:, 1]
            lo, hi = e.min(1), e.max(1)
            code = lo.astype(np.int64) * (wid.max() + 1) + hi
            uc, inv, cnt = np.unique(code, return_inverse=True, return_counts=True)
            sel = ok & (cnt[inv.reshape(-1)] == 1)
            for k in np.nonzero(sel)[0]:
                a, b = f.A[ei[k, 0], :3], f.A[ei[k, 1], :3]
                P0.append(a)
                P1.append(b)
                F.append(si)
                IN.append(f.A[third[k], :3])
        self.E = dict(p0=np.array(P0), p1=np.array(P1), f=np.array(F, dtype=np.int64), tv=np.array(IN))
        self.stats["boundary_edges"] = len(F)

    # --- 3. collinear overlap pairs
    def match_edges(self):
        E = self.E
        n = len(E["f"])
        v = E["p1"] - E["p0"]
        ln = np.linalg.norm(v, axis=1)
        d = v / np.maximum(ln, 1e-12)[:, None]
        # canonical sign: first component (by rounded |.| descending, then index) positive
        ad = np.round(np.abs(d), 3)
        # argmax of rounded |d| (first max wins, i.e. lowest index)
        lead = np.argmax(ad, axis=1)
        sgn = np.sign(d[np.arange(n), lead])
        sgn[sgn == 0] = 1
        d = d * sgn[:, None]
        keep = ln > 0.5
        # direction clusters
        keyd = np.round(d * 200).astype(np.int64)
        uk, ukfirst, uinv = np.unique(keyd, axis=0, return_index=True, return_inverse=True)
        uinv = uinv.reshape(-1)
        reps = []
        rep_of_key = np.zeros(len(uk), dtype=np.int64)
        for i in range(len(uk)):
            dv = d[ukfirst[i]]
            if reps:
                dots = np.array(reps) @ dv
                j = int(dots.argmax())
                if dots[j] > 1 - 2e-5:
                    rep_of_key[i] = j
                    continue
            reps.append(dv)
            rep_of_key[i] = len(reps) - 1
        did = rep_of_key[uinv]
        reps = np.array(reps)
        D = reps[did]
        # the perpendicular offset of a line, expressed in a basis of the plane orthogonal to the representative
        h = np.zeros_like(D)
        h[np.arange(n), np.argmin(np.abs(D), axis=1)] = 1.0
        U = np.cross(D, h)
        U /= np.linalg.norm(U, axis=1)[:, None]
        V = np.cross(D, U)
        ou = (E["p0"] * U).sum(1)
        ov = (E["p0"] * V).sum(1)
        # The representative direction D of a cluster can be tilted by up to ~0.006 rad against an edge's own direction, so the
        # projected offsets of a long edge drift by tilt*length. Every edge therefore covers all cells touched by its
        # projected segment (plus a margin), and the exact collinearity test below uses the edge's own direction.
        cell, margin = 0.4, 0.25
        ou1 = (E["p1"] * U).sum(1)
        ov1 = (E["p1"] * V).sum(1)
        cells = collections.defaultdict(list)
        for i in range(n):
            if not keep[i]:
                continue
            for cu in range(int(np.floor((min(ou[i], ou1[i]) - margin) / cell)), int(np.floor((max(ou[i], ou1[i]) + margin) / cell)) + 1):
                for cv in range(int(np.floor((min(ov[i], ov1[i]) - margin) / cell)), int(np.floor((max(ov[i], ov1[i]) + margin) / cell)) + 1):
                    cells[(int(did[i]), cu, cv)].append(i)
        cand = set()
        for lst in cells.values():
            for a_ in range(len(lst)):
                for b_ in range(a_ + 1, len(lst)):
                    cand.add((lst[a_], lst[b_]) if lst[a_] < lst[b_] else (lst[b_], lst[a_]))
        own = v / np.maximum(ln, 1e-12)[:, None]
        pairs = []
        seams = collections.defaultdict(list)
        self.coplanar_pairs = set()
        for i, j in sorted(cand):
            if E["f"][j] == E["f"][i]:
                continue
            q, dd = E["p0"][i], own[i]
            ok = True
            tj = []
            for p in (E["p0"][j], E["p1"][j]):
                w = p - q
                if np.linalg.norm(w - (w @ dd) * dd) > 0.15:
                    ok = False
                    break
                tj.append(float(w @ dd))
            if not ok:
                continue
            lo, hi = max(0.0, min(tj)), min(float(ln[i]), max(tj))
            if hi - lo < 0.25:
                continue
            fi, fj = self.faces[E["f"][i]], self.faces[E["f"][j]]
            if float(fi.n @ fj.n) > 1 - 1e-4 and abs(fi.d - fj.d) < 0.1:
                # coplanar neighbours across this edge: the stretch is a seam inside one flat surface, not an edge
                self.coplanar_pairs.add((fi.si, fj.si))
                ti = E["tv"][i] - q
                tk = E["tv"][j] - q
                si = ti - (ti @ dd) * dd
                sk = tk - (tk @ dd) * dd
                if float(si @ sk) < 0:
                    seams[i].append((q + dd * lo, q + dd * hi))
                    seams[j].append((q + dd * lo, q + dd * hi))
            pairs.append((i, j, q + dd * lo, q + dd * hi))
        # A convex pair stretch that also lies on a seam of either face (e.g. the top of a step that continues flush into the
        # next block while the riser below it is one long face) is hidden inside the solid there: no bevel over it.
        out = []
        for i, j, pa, pb in pairs:
            if float(self.faces[E["f"][i]].n @ self.faces[E["f"][j]].n) > 1 - 1e-4:
                out.append((i, j, pa, pb))  # coplanar pairs only feed the rej_coplanar statistic
                continue
            ln_ = float(np.linalg.norm(pb - pa))
            dd = (pb - pa) / max(ln_, 1e-12)
            cut = sorted((max(0.0, float(min((s0 - pa) @ dd, (s1 - pa) @ dd))), min(ln_, float(max((s0 - pa) @ dd, (s1 - pa) @ dd))))
                         for s0, s1 in seams.get(i, []) + seams.get(j, []))
            segs, t = [], 0.0
            for c0, c1 in cut:
                if c1 <= c0:
                    continue
                if c0 - t >= 0.25:
                    segs.append((t, c0))
                t = max(t, c1)
            if ln_ - t >= 0.25:
                segs.append((t, ln_))
            if len(segs) == 1 and segs[0] == (0.0, ln_):
                out.append((i, j, pa, pb))
                continue
            if segs:
                self.stats["pairs_seam_trimmed"] += 1
            else:
                self.stats["pairs_seam_removed"] += 1
            out.extend((i, j, pa + dd * s0, pa + dd * s1) for s0, s1 in segs)
        pairs = out
        self.pairs = pairs
        self.stats["edge_pairs_collinear_overlap"] = len(pairs)

    # --- 4. classify pairs and build groups
    def build_groups(self):
        a = self.a
        cos_min, cos_max = math.cos(math.radians(a.max_angle)), math.cos(math.radians(a.min_angle))
        planes = {}

        def plane_id(f):
            k = (int(round(f.n[0] * 500)), int(round(f.n[1] * 500)), int(round(f.n[2] * 500)), int(round(f.d / 0.25)))
            return planes.setdefault(k, len(planes))

        acc = {}
        for i, j, pa, pb in self.pairs:
            fa, fb = self.faces[self.E["f"][i]], self.faces[self.E["f"][j]]
            c = float(fa.n @ fb.n)
            if c > 1 - 1e-4:
                self.stats["rej_coplanar"] += 1
                continue
            if not (cos_min <= c <= cos_max):
                self.stats["rej_angle"] += 1
                continue
            if not (fb.n @ (fa.centroid) - fb.d < -0.05 and fa.n @ (fb.centroid) - fa.d < -0.05):
                self.stats["rej_concave"] += 1
                continue
            ia, ib = plane_id(fa), plane_id(fb)
            if ia > ib:
                fa, fb, ia, ib = fb, fa, ib, ia
            g = acc.setdefault((ia, ib), dict(fa=fa, fb=fb, seg=[], fA={}, fB={}))
            g["seg"].append((pa, pb))
            self.stats["pairs_convex"] += 1
            # remember which faces contribute (and their t extents later)
            g["fA"].setdefault(fa.si, fa)
            g["fB"].setdefault(fb.si, fb)
            g.setdefault("fseg", []).append((fa.si, fb.si, pa, pb))
        # per plane pair: line frame from the planes, merge the overlap intervals
        for key, g in acc.items():
            fa, fb = g["fa"], g["fb"]
            nA, nB = fa.n, fb.n
            d, P0 = line_frame(nA, fa.d, nB, fb.d)
            ivs = []
            for pa, pb in g["seg"]:
                t0, t1 = float((pa - P0) @ d), float((pb - P0) @ d)
                ivs.append((min(t0, t1), max(t0, t1)))
            ivs.sort()
            merged = []
            for lo, hi in ivs:
                if merged and lo <= merged[-1][1] + 1.0:
                    merged[-1][1] = max(merged[-1][1], hi)
                else:
                    merged.append([lo, hi])
            for lo, hi in merged:
                gr = Group()
                gr.d, gr.P0, gr.nA, gr.nB, gr.lo, gr.hi = d, P0, nA, nB, lo, hi
                gr.pk = key
                fAs, fBs = {}, {}
                for sa, sb, pa, pb in g["fseg"]:
                    t0, t1 = sorted((float((pa - P0) @ d), float((pb - P0) @ d)))
                    if t1 < lo - 1e-3 or t0 > hi + 1e-3:
                        continue
                    for store, sid in ((fAs, sa), (fBs, sb)):
                        e = store.setdefault(sid, [t0, t1])
                        e[0], e[1] = min(e[0], t0), max(e[1], t1)
                gr.fA, gr.fB = fAs, fBs
                self.groups.append(gr)
        self.stats["groups_candidate"] = len(self.groups)

    # --- 5. group checks + processing
    def prepare(self, gr):
        a = self.a
        if gr.hi - gr.lo < a.min_length:
            return "rej_short"
        cA = np.mean([self.faces[s].centroid for s in gr.fA], axis=0)
        cB = np.mean([self.faces[s].centroid for s in gr.fB], axis=0)
        gr.wA = unit(np.cross(gr.d, gr.nA))
        if gr.wA @ (cA - gr.P0) < 0:
            gr.wA = -gr.wA
        gr.wB = unit(np.cross(gr.d, gr.nB))
        if gr.wB @ (cB - gr.P0) < 0:
            gr.wB = -gr.wB
        if not (gr.nA @ gr.wB < -1e-3 and gr.nB @ gr.wA < -1e-3):
            return "rej_concave_group"
        dmin = 1e18  # smallest extent of any face of the run, measured from the edge
        for store, w in ((gr.fA, gr.wA), (gr.fB, gr.wB)):
            for s in store:
                f = self.faces[s]
                dmin = min(dmin, float(((f.A[:, :3] - gr.P0) @ w).max()))
        gr.r = min(a.radius, 0.45 * dmin)  # adaptive radius: ledge tops and plinth steps get a smaller bevel
        if gr.r < a.min_radius - 1e-9:
            return "rej_thin_face"
        gr.theta = math.acos(max(-1.0, min(1.0, float(gr.nA @ gr.nB))))
        gr.R_over_c = 1.0 / math.tan(gr.theta / 2)
        gr.corner = [False, False]
        gr.corner_te = [None, None]
        gr.mitre = [None, None]  # run end meeting another run at a reflex bend of the shared plane (find_mitres)
        gr.wall_pl = [None, None]  # (normal, d) of the wall plane at a wall end
        gr.wall_cap = [True, True]  # a wall end needs a cap unless the wall face already covers the notch
        gr.wall = [False, False]  # run end butts into a wall: full radius up to the end, a cap fills the notch (find_wall_ends)
        self.layout(gr)
        return None

    def layout(self, gr):
        """Cut profile c(t) (bps/cvals), taper and the extent of the strip rows [te_lo, te_hi] from r and the corner flags.
        A corner end is not tapered: the cut stays at full radius up to the run end, the strip stops r short of it and the
        corner patch closes the gap."""
        a, r = self.a, gr.r
        L = gr.hi - gr.lo
        gr.tap = min(2 * r if a.taper is None else a.taper, L / 3)
        cl, ch = gr.corner
        gr.te_lo = (gr.corner_te[0] if gr.corner_te[0] is not None else gr.lo + r) if cl else gr.lo
        gr.te_hi = (gr.corner_te[1] if gr.corner_te[1] is not None else gr.hi - r) if ch else gr.hi
        fl = cl or gr.wall[0] or gr.mitre[0] is not None  # full radius up to the end (box corner, wall end, mitre): no taper
        fh = ch or gr.wall[1] or gr.mitre[1] is not None
        bps, cv = [gr.lo], [r if fl else 0.0]
        if not fl:
            bps.append(gr.lo + gr.tap)
            cv.append(r)
        if not fh:
            bps.append(gr.hi - gr.tap)
            cv.append(r)
        bps.append(gr.hi)
        cv.append(r if fh else 0.0)
        gr.bps, gr.cvals = [bps[0]], [cv[0]]
        for b, c in zip(bps[1:], cv[1:]):
            if b - gr.bps[-1] > 1e-6:
                gr.bps.append(b)
                gr.cvals.append(c)

    def c_at(self, gr, t):
        if t <= gr.bps[0]:
            return gr.cvals[0]
        if t >= gr.bps[-1]:
            return gr.cvals[-1]
        for k in range(len(gr.bps) - 1):
            if gr.bps[k] <= t <= gr.bps[k + 1]:
                ta, tb = gr.bps[k], gr.bps[k + 1]
                return gr.cvals[k] + (gr.cvals[k + 1] - gr.cvals[k]) * (t - ta) / (tb - ta)
        return 0.0

    # --- 5b. box corners: three convex runs ending at one vertex
    def find_corners(self, order):
        ends = []
        for gid in order:
            gr = self.groups[gid]
            if gr.hi - gr.lo >= 2 * gr.r + 1.0:
                ends.append((gid, 0, gr.P0 + gr.d * gr.lo))
                ends.append((gid, 1, gr.P0 + gr.d * gr.hi))
        grid = collections.defaultdict(list)
        for k, (_g, _e, p) in enumerate(ends):
            grid[tuple(np.floor(p / 2).astype(int))].append(k)
        normals = {}
        for gid in order:
            gr = self.groups[gid]
            normals[gr.pk[0]], normals[gr.pk[1]] = gr.nA, gr.nB
        self.corners, seen = [], set()
        self.rej_log = []
        for k, (_g, _e, p) in enumerate(ends):
            if k in seen:
                continue
            c0 = np.floor(p / 2).astype(int)
            near = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                    for j in grid.get((c0[0] + dx, c0[1] + dy, c0[2] + dz), []) if np.linalg.norm(ends[j][2] - p) < 0.75]
            seen.update(near)
            if len(near) < 3:
                if len(near) == 2:
                    self.rej_log.append(("two", p))
                continue
            if len(near) != 3:
                self.stats["corner_rej_not_three_runs"] += 1
                self.rej_log.append(("n%d" % len(near), p))
                continue
            gids = [ends[j][0] for j in near]
            pks = [self.groups[g].pk for g in gids]
            planes = set(x for pk in pks for x in pk)
            if len(set(gids)) != 3 or len(planes) != 3 or len(set(pks)) != 3:
                self.stats["corner_rej_not_a_box_vertex"] += 1
                self.rej_log.append(("nobox", p))
                continue
            ok = True
            for j in near:
                gr = self.groups[ends[j][0]]
                n3 = normals[next(iter(planes - set(gr.pk)))]
                u = gr.d if ends[j][1] == 0 else -gr.d  # direction of the run away from the vertex
                if float(u @ n3) > -0.985:  # must be perpendicular to the third plane and run into the solid (a box vertex)
                    ok = False
            if not ok:
                self.stats["corner_rej_not_orthogonal"] += 1
                self.rej_log.append(("nonorth", p))
                continue
            self.corners.append(dict(ends=[(ends[j][0], ends[j][1]) for j in near], pos=np.mean([ends[j][2] for j in near], axis=0),
                                     planes=sorted(planes)))
        changed = True
        while changed:  # the three runs of a corner share one radius
            changed = False
            for cr in self.corners:
                rc = min(self.groups[g].r for g, _e in cr["ends"])
                for g, _e in cr["ends"]:
                    if self.groups[g].r > rc + 1e-9:
                        self.groups[g].r = rc
                        changed = True
        good = []
        for cr in self.corners:
            te = self.corner_extents(cr)
            if te is None:
                self.stats["corner_rej_skewed"] += 1
                self.rej_log.append(("skewed", cr["pos"]))
                continue
            for (g, e), t in zip(cr["ends"], te):
                self.groups[g].corner[e] = True
                self.groups[g].corner_te[e] = t
            good.append(cr)
        self.corners = good
        for gid in order:
            self.layout(self.groups[gid])
        self.stats["corners_found"] = len(self.corners)

    def corner_extents(self, cr):
        """Where the strip of each run of a box corner has to stop: the corner of the clipped face, i.e. the intersection of
        the two cut lines on each plane, expressed as t along the run. None when the two sides of a run disagree (skewed
        planes: the end row would not be planar and would leave a crack)."""
        per = {}  # group -> list of t values (one per side)
        for plane in cr["planes"]:
            hits = [(g, e) for g, e in cr["ends"] if plane in self.groups[g].pk]
            if len(hits) != 2:
                return None
            rows, rhs, face = [], [], None
            for g, e in hits:
                gr = self.groups[g]
                side_a = gr.pk[0] == plane
                w, store = (gr.wA, gr.fA) if side_a else (gr.wB, gr.fB)
                face = self.faces[next(iter(store))]
                rows.append(w)
                rhs.append(gr.r + float(w @ gr.P0))
            rows.append(face.n)
            rhs.append(face.d)
            try:
                X = np.linalg.solve(np.array(rows), np.array(rhs))
            except np.linalg.LinAlgError:
                return None
            for g, e in hits:
                gr = self.groups[g]
                per.setdefault((g, e), []).append(float((X - gr.P0) @ gr.d))
        out = []
        for g, e in cr["ends"]:
            v = per.get((g, e), [])
            if len(v) != 2 or abs(v[0] - v[1]) > 0.05:
                return None
            t = 0.5 * (v[0] + v[1])
            gr = self.groups[g]
            if abs(t - (gr.lo + gr.r if e == 0 else gr.hi - gr.r)) > 0.5 * gr.r or not (gr.lo < t < gr.hi):
                return None
            out.append(t)
        return out

    def revert_broken_corners(self):
        """A corner whose runs were not all accepted (overlap/coverage) falls back to tapered ends."""
        keep = []
        for cr in self.corners:
            if all(self.groups[g].ok for g, _e in cr["ends"]):
                keep.append(cr)
                continue
            self.stats["corners_reverted"] += 1
            for g, e in cr["ends"]:
                gr = self.groups[g]
                if gr.ok:
                    gr.corner[e] = False
                    self.layout(gr)
        self.corners = keep

    def snap_corner_ends(self):
        """Where the faces are not exactly perpendicular the strip must stop at the real corner vertex of the clipped faces
        (the end of the cut polyline), not r short of the run end."""
        for gid, gr in enumerate(self.groups):
            if not gr.ok:
                continue
            for e in (0, 1):
                if not gr.corner[e]:
                    continue
                vals = []
                for store in (gr.fA, gr.fB):
                    ts = [t for sid in store for g2, t, _p in self.faces[sid].cutverts if g2 == gid]
                    if ts:
                        vals.append(min(ts) if e == 0 else max(ts))
                if not vals:
                    continue
                te = float(np.mean(vals))
                nominal = gr.te_lo if e == 0 else gr.te_hi
                if abs(te - nominal) > 0.5 * gr.r:
                    self.stats["corner_end_snap_rejected"] += 1
                    continue
                if e == 0:
                    gr.te_lo = te
                else:
                    gr.te_hi = te

    def rebuild_cutverts(self):
        """Every vertex of the final clipped faces that lies on a run's cut line becomes a strip row of that run."""
        for gid, gr in enumerate(self.groups):
            if not gr.ok:
                continue
            for store, w in ((gr.fA, gr.wA), (gr.fB, gr.wB)):
                for sid in store:
                    f = self.faces[sid]
                    for P in f.polys:
                        sp = (P[:, :3] - gr.P0) @ w
                        tp = (P[:, :3] - gr.P0) @ gr.d
                        for q in range(len(P)):
                            if gr.lo - 1e-6 <= tp[q] <= gr.hi + 1e-6 and abs(sp[q] - self.c_at(gr, tp[q])) < 1e-6:
                                f.cutverts.append((gid, float(tp[q]), P[q, :3].copy()))

    @staticmethod
    def profile(gr, side):
        """Breakpoints/cut depths of the run as seen from side 0 (plane pk[0]) or 1: at a mitre end the cut continues r past
        the run end on the plane the two mitred runs share, so the two cuts together clear the square at the reflex bend."""
        bps, cv = list(gr.bps), list(gr.cvals)
        if gr.mitre[0] is not None and gr.mitre[0]["P"] == gr.pk[side]:
            bps.insert(0, gr.lo - gr.r)
            cv.insert(0, gr.r)
        if gr.mitre[1] is not None and gr.mitre[1]["P"] == gr.pk[side]:
            bps.append(gr.hi + gr.r)
            cv.append(gr.r)
        return bps, cv

    def cut_face(self, f, gr, w, gid, side):
        """Clip every polygon of face f against s >= c(t) for the group."""
        f.ensure_polys()
        bps, cvals = self.profile(gr, side)
        r = gr.r
        out = []
        P0, d = gr.P0, gr.d
        for P in f.polys:
            s = (P[:, :3] - P0) @ w
            if s.max() <= 1e-9:
                out.append(P)  # behind the cut line (a face joined by extend_store that wraps around the bend): not ours
                continue
            if s.min() < -1e-9:
                P, P_back = split_plane(P, s)
                if P_back is not None:
                    out.append(P_back)
                if P is None:
                    continue
                s = (P[:, :3] - P0) @ w
            t = (P[:, :3] - P0) @ d
            if s.min() >= r - 1e-9 or t.max() <= bps[0] + 1e-9 or t.min() >= bps[-1] - 1e-9:
                out.append(P)
                continue
            up, low = split_plane(P, s - r)
            pieces = [low] if low is not None else []
            for b in bps:
                nxt = []
                for pc in pieces:
                    tp = (pc[:, :3] - P0) @ d
                    p1, p2 = split_plane(pc, tp - b)
                    nxt.extend(x for x in (p1, p2) if x is not None)
                pieces = nxt
            kept, online = [], []
            for pc in pieces:
                tp = (pc[:, :3] - P0) @ d
                tm = float(tp.mean())
                if tm <= bps[0] or tm >= bps[-1]:
                    kept.append(pc)
                else:
                    k = next((k for k in range(len(bps) - 1) if bps[k] <= tm <= bps[k + 1]), None)
                    if k is None:
                        kept.append(pc)
                        continue
                    ta, tb = bps[k], bps[k + 1]
                    c0, c1 = cvals[k], cvals[k + 1]
                    sp = (pc[:, :3] - P0) @ w
                    sd = sp - (c0 + (c1 - c0) * (tp - ta) / (tb - ta))
                    pos, _neg = split_plane(pc, sd)
                    if pos is None:
                        continue
                    kept.append(pos)
                for q in pc:
                    if abs(float((q[:3] - P0) @ w) - r) < 1e-7:
                        online.append(q)
            if up is not None:
                up = self.insert_online(up, online, P0, w, d, r)
                out.append(up)
            out.extend(kept)
        f.polys = out

    @staticmethod
    def insert_online(up, online, P0, w, d, r):
        if not online:
            return up
        s = (up[:, :3] - P0) @ w
        on = np.nonzero(np.abs(s - r) < 1e-7)[0]
        if len(on) != 2:
            return up
        k = len(up)
        i0, i1 = int(on[0]), int(on[1])
        if (i0 + 1) % k == i1:
            a_i, b_i = i0, i1
        elif (i1 + 1) % k == i0:
            a_i, b_i = i1, i0
        else:
            return up
        ta = float((up[a_i, :3] - P0) @ d)
        tb = float((up[b_i, :3] - P0) @ d)
        lo, hi = min(ta, tb), max(ta, tb)
        ins, seen = [], []
        for q in online:
            tq = float((q[:3] - P0) @ d)
            if lo + 1e-6 < tq < hi - 1e-6 and not any(abs(tq - x) < 1e-6 for x in seen):
                seen.append(tq)
                ins.append((tq, q))
        if not ins:
            return up
        ins.sort(key=lambda x: x[0], reverse=ta > tb)
        rows = list(up)
        rows[b_i:b_i] = [q for _t, q in ins]
        return np.array(rows)

    def thin_rows(self, gr, ts, polys, actual_end):
        """Keep the taper breakpoints and corner ends, and add a row only where a cut-line vertex of a clipped face deviates
        by more than --row-tol from the line through its neighbouring rows (collinear vertices become T-junctions)."""
        forced = [0, len(ts) - 1]
        for b in [gr.te_lo, gr.te_hi] + [b for b in gr.bps if gr.te_lo - 1e-6 <= b <= gr.te_hi + 1e-6]:
            forced.append(min(range(len(ts)), key=lambda i: abs(ts[i] - b)))
        keep = sorted(set(forced))
        todo = [(keep[k], keep[k + 1]) for k in range(len(keep) - 1)]
        while todo:
            i0, i1 = todo.pop()
            if i1 - i0 < 2:
                continue
            ta, tb = ts[i0], ts[i1]
            best, bd = None, self.a.row_tol
            for poly in polys:
                tk = poly[0]
                if len(tk) < 2:
                    continue
                pa, pb = actual_end(poly, ta, None), actual_end(poly, tb, None)
                if pa is None or pb is None:
                    continue
                for i in range(i0 + 1, i1):
                    t = ts[i]
                    pt = actual_end(poly, t, None)
                    if pt is None:
                        continue
                    u = (t - ta) / (tb - ta)
                    dev = float(np.linalg.norm(pt - (pa + u * (pb - pa))))
                    if dev > bd:
                        best, bd = i, dev
            if best is not None:
                keep.append(best)
                todo.append((i0, best))
                todo.append((best, i1))
        self.stats["strip_rows_candidate"] += len(ts)
        self.stats["strip_rows_kept"] += len(set(keep))
        return [ts[i] for i in sorted(set(keep))]

    def build_strip(self, gr, gid):
        a = self.a
        rows = set(round(b, 6) for b in gr.bps if gr.te_lo - 1e-6 <= b <= gr.te_hi + 1e-6)
        rows.update((round(gr.te_lo, 6), round(gr.te_hi, 6)))
        for store in (gr.fA, gr.fB):
            for s in store:
                for g2, t, _p in self.faces[s].cutverts:
                    if g2 == gid and gr.te_lo - 1e-6 <= t <= gr.te_hi + 1e-6:
                        rows.add(round(t, 6))
        ts = sorted(rows)
        merged = [ts[0]]
        for t in ts[1:]:
            if t - merged[-1] > 5e-4:
                merged.append(t)
        ts = merged
        N = max(1, a.segments)
        phis = sorted(set([k / N for k in range(N + 1)] + [0.5]))
        phisA = [p for p in phis if p <= 0.5 + 1e-9]
        phisB = [p for p in phis if p >= 0.5 - 1e-9]
        theta = gr.theta
        rowsd = []

        def polyline(store):
            """Actual cut-line vertices of the clipped faces (t, position), sorted by t."""
            pts = {}
            for sid in store:
                for g2, t, pos in self.faces[sid].cutverts:
                    if g2 == gid:
                        pts.setdefault(round(t, 4), pos)
            k = sorted(pts)
            return np.array(k), (np.array([pts[x] for x in k]) if k else np.zeros((0, 3)))

        polyA, polyB = polyline(gr.fA), polyline(gr.fB)

        def actual_end(poly, t, fallback):
            """Point of the real cut line at t: exact cut vertex or linear interpolation between neighbours."""
            tk, pk = poly
            if len(tk) < 2:
                return fallback
            i = int(np.searchsorted(tk, t))
            if i < len(tk) and abs(tk[i] - t) < 5e-4:
                return pk[i]
            if i > 0 and abs(tk[i - 1] - t) < 5e-4:
                return pk[i - 1]
            if i == 0 or i >= len(tk):
                return fallback
            u = (t - tk[i - 1]) / (tk[i] - tk[i - 1])
            return pk[i - 1] + u * (pk[i] - pk[i - 1])

        if a.row_tol > 0 and len(ts) > 2:
            ts = self.thin_rows(gr, ts, (polyA, polyB), actual_end)

        # wall ends: the last row is slid along the run onto the wall plane and ends exactly at the end vertices of the two
        # clipped cut lines (the wall can be a few degrees off perpendicular, so the two faces end at different t)
        end_row = {}
        for e in (0, 1):
            if not gr.wall[e]:
                continue
            ex = [(pl[0][0] if e == 0 else pl[0][-1]) for pl in (polyA, polyB) if len(pl[0])]
            tref = (max(ex) if e == 0 else min(ex)) if ex else (ts[0] if e == 0 else ts[-1])
            ts = ([tref] + [t for t in ts if t > tref + 5e-4]) if e == 0 else ([t for t in ts if t < tref - 5e-4] + [tref])
            end_row[round(tref, 6)] = e

        for t in ts:
            c = self.c_at(gr, t)
            R = c * gr.R_over_c
            E = gr.P0 + gr.d * t
            K = E + c * gr.wA - R * gr.nA
            Kb = E + c * gr.wB - R * gr.nB
            if np.abs(K - Kb).max() > 1e-6:
                self.stats["strip_center_mismatch"] += 1
            nrm = [slerp(gr.nA, gr.nB, p, theta) for p in phis]
            # the face vertices sit up to ~0.05 off the exact plane intersection: pull the arc ends onto the real cut
            # lines (the offset fades linearly over the arc) so the strip meets the clipped faces without a crack
            tA, tB = K + R * nrm[0], K + R * nrm[-1]
            dA = actual_end(polyA, t, tA) - tA
            dB = actual_end(polyB, t, tB) - tB
            pts = {p: K + R * nm + (1 - p) * dA + p * dB for p, nm in zip(phis, nrm)}
            if round(t, 6) in end_row:
                nW, dW = gr.wall_pl[end_row[round(t, 6)]]
                for p in phis:
                    pts[p] = pts[p] + ((dW - float(nW @ pts[p])) / float(nW @ gr.d)) * gr.d
                for p, pl in ((phis[0], polyA), (phis[-1], polyB)):
                    if len(pl[0]):
                        q_ = pl[1][0] if end_row[round(t, 6)] == 0 else pl[1][-1]
                        if np.linalg.norm(q_ - pts[p]) > 0.3:
                            self.stats["wall_end_row_mismatch"] += 1
                        pts[p] = q_
            nms = dict(zip(phis, nrm))
            rowsd.append((t, c, pts, nms))
        for e in (0, 1):  # mitre ends: one more row, slid along the run onto the bisector plane and shared with the partner run
            mt = gr.mitre[e]
            if mt is None:
                continue
            base = rowsd[0] if e == 0 else rowsd[-1]
            u = gr.d if e == 0 else -gr.d
            p_first = gr.pk[0] == mt["P"]  # the shared plane is side A (phi = 0)
            key = lambda p: round(p if p_first else 1.0 - p, 6)  # distance from the shared plane's side
            slid = {key(p): X - (float(mt["nPi"] @ (X - mt["V"])) / float(mt["nPi"] @ u)) * u for p, X in base[2].items()}
            sh = mt["shared"]
            if "pts" not in sh:
                # snap the arc end on the shared plane to the corner vertex of the clipped faces (where both cut lines meet)
                best, bd = None, 0.3
                for sid in (gr.fA if p_first else gr.fB):
                    for P in self.faces[sid].polys:
                        dd = np.linalg.norm(P[:, :3] - slid[0.0], axis=1)
                        if dd.min() < bd:
                            best, bd = P[int(dd.argmin()), :3].copy(), float(dd.min())
                if best is None:
                    self.stats["mitre_corner_vertex_missing"] += 1
                else:
                    slid[0.0] = best
                sh["pts"] = slid
            elif max(float(np.linalg.norm(sh["pts"][k] - slid[k])) for k in slid) > 0.1:
                self.stats["mitre_asymmetric"] += 1
            tl = base[0] - gr.r if e == 0 else base[0] + gr.r
            row = (tl, base[1], {p: sh["pts"][key(p)] for p in base[2]}, base[3])
            if e == 0:
                rowsd.insert(0, row)
            else:
                rowsd.append(row)
        gr.row_first, gr.row_last = rowsd[0], rowsd[-1]

        def pick(store, tm):
            best, bd = None, 1e18
            for s, (t0, t1) in store.items():
                dd = 0.0 if t0 - 1e-3 <= tm <= t1 + 1e-3 else min(abs(tm - t0), abs(tm - t1))
                if dd < bd:
                    best, bd = s, dd
            return self.faces[best]

        cache = {}
        pairs = {}

        def pair_k(fa, fb, tm):
            """Integer texture shift k for a face pair (None = keep the seam). Decided once per pair and run."""
            key = (fa.si, fb.si)
            if key in pairs:
                return pairs[key]
            k = None
            if a.uv_mode != "morph":
                pass
            elif fa.surf["shader"] != fb.surf["shader"]:
                self.stats["uv_seam_pairs_other_shader"] += 1
            else:
                ga = math.sqrt(abs(np.linalg.det(fa.fit[:2, :2])))
                gb = math.sqrt(abs(np.linalg.det(fb.fit[:2, :2])))
                if min(ga, gb) < 1e-9 or max(ga, gb) / min(ga, gb) > 1.5:
                    self.stats["uv_seam_pairs_scale_fallback"] += 1
                else:
                    pm = gr.P0 + gr.d * tm
                    dst = fa.eval_map(pm)[0] - fb.eval_map(pm)[0]
                    k = np.rint(dst)
                    self.stats["uv_residual_sum"] += float(np.abs(dst - k).max())  # leftover st offset the morph absorbs
                    self.stats["uv_morph_pairs"] += 1
            pairs[key] = k
            return k

        def unfold(f, rowpts, phi):
            """Point on f's plane at the arc length of the strip row from f's cut line, continuing straight into the corner."""
            ph = sorted(rowpts)
            sideA = f.si in gr.fA
            seq = ph if sideA else ph[::-1]
            tgt = phi
            arc = 0.0
            for p0, p1 in zip(seq, seq[1:]):
                arc += float(np.linalg.norm(rowpts[p1] - rowpts[p0]))
                if abs(p1 - tgt) < 1e-9:
                    break
            if tgt == seq[0]:
                arc = 0.0
            c = rowpts[seq[0]]
            ed = gr.P0 + gr.d * float((c - gr.P0) @ gr.d)
            w = ed - c
            w = w - (w @ f.n) * f.n
            nw = float(np.linalg.norm(w))
            return c + (w / nw) * arc if nw > 1e-9 else c

        def vert(f, x, nrm, phi, fo, k, rowpts=None):
            key = (f.si, fo.si, tuple(np.round(x, 5)), round(phi, 6))
            v = cache.get(key)
            if v is None:
                if a.uv_mode == "align" and rowpts is not None:
                    st, lm = f.eval_map(unfold(f, rowpts, phi))
                else:
                    st, lm = f.eval_map(x - ((x - gr.P0) @ f.n) * f.n)
                if k is not None:
                    fa_, fb_ = (f, fo) if f.si in gr.fA else (fo, f)
                    sa, sb = fa_.eval_map(x)[0], fb_.eval_map(x)[0]
                    e = phi * phi * (3 - 2 * phi)  # smoothstep
                    st = (1 - e) * sa + e * (sb + k)
                v = np.concatenate([x, st, lm, nrm, f.nearest_color(x)])
                cache[key] = v
            return v

        added = 0
        for ri in range(len(rowsd) - 1):
            ra, rb = rowsd[ri], rowsd[ri + 1]
            if ra[1] == 0.0 and rb[1] == 0.0:
                continue
            tm = 0.5 * (ra[0] + rb[0])
            for half, store, phs in (("A", gr.fA, phisA), ("B", gr.fB, phisB)):
                f = pick(store, tm)
                fo = pick(gr.fB if half == "A" else gr.fA, tm)
                kk = pair_k(f, fo, tm) if half == "A" else pair_k(fo, f, tm)
                for k in range(len(phs) - 1):
                    q00 = vert(f, ra[2][phs[k]], ra[3][phs[k]], phs[k], fo, kk, ra[2])
                    q01 = vert(f, ra[2][phs[k + 1]], ra[3][phs[k + 1]], phs[k + 1], fo, kk, ra[2])
                    q10 = vert(f, rb[2][phs[k]], rb[3][phs[k]], phs[k], fo, kk, rb[2])
                    q11 = vert(f, rb[2][phs[k + 1]], rb[3][phs[k + 1]], phs[k + 1], fo, kk, rb[2])
                    for tri in ((q00, q10, q11), (q00, q11, q01)):
                        T = np.array(tri)
                        cr = np.cross(T[1, :3] - T[0, :3], T[2, :3] - T[0, :3])
                        if np.linalg.norm(cr) < 1e-6:
                            self.stats["strip_tris_degenerate_skipped"] += 1
                            continue
                        navg = T[:, 7:10].sum(0)
                        if f.winding * float(cr @ navg) < 0:
                            T = T[[0, 2, 1]]
                        f.strip.append(T)
                        added += 1
        return added

    # --- 5d. mitres
    def drop_ext(self, gr, e):
        """Take back the neighbouring faces of the shared plane that extend_store added for this end."""
        m = gr.mitre[e]
        for sid in m["added"]:
            (gr.fA if gr.pk[0] == m["P"] else gr.fB).pop(sid, None)
        gr.mitre[e] = None
        self.layout(gr)

    def clear_mitre(self, gr, e):
        g2, e2 = gr.mitre[e]["partner"]
        p = self.groups[g2]
        self.drop_ext(gr, e)
        if p.mitre[e2] is not None:
            self.drop_ext(p, e2)

    def extend_store(self, gr, e):
        """The corner square past a mitre end can belong to another face of the shared plane P than the run's own: those
        faces join the run's face set on the P side (extents [lo-r, lo] / [hi, hi+r]) so they are cut too."""
        m = gr.mitre[e]
        p_first = gr.pk[0] == m["P"]
        store, w = (gr.fA, gr.wA) if p_first else (gr.fB, gr.wB)
        f0 = self.faces[next(iter(store))]
        u = gr.d if e == 0 else -gr.d
        r = gr.r
        ss = [(a_, b_) for a_ in (0.1, 0.5, 0.9) for b_ in (0.1, 0.5, 0.9)]
        pts = [m["V"] - u * r * a_ + w * r * b_ for a_, b_ in ss]
        m["added"] = []
        for si, f in self.faces.items():
            if si in store or f.bad or abs(float(f.n @ f0.n) - 1) > 1e-4 or abs(f.d - f0.d) > 0.1:
                continue
            if any(self.point_in_face(f, x) for x in pts):
                store[si] = [gr.lo - r, gr.lo] if e == 0 else [gr.hi, gr.hi + r]
                m["added"].append(si)

    def find_mitres(self, order):
        """Two runs of one plane P that end at the same vertex and bend around a reflex (L-shaped) outline of P: the cut band
        of each runs on through the corner square, the two strips stop at the bisector plane and share that end row, so the
        rounded edge goes around the bend without a taper. Needs equal radius and dihedral (the bend is then mirror
        symmetric) and orthogonal runs; anything else keeps the taper."""
        self.mitres = []
        if not self.a.mitre:
            return
        ends = []
        for gid in order:
            gr = self.groups[gid]
            if gr.hi - gr.lo < 2 * gr.r + 1.0:
                continue
            for e in (0, 1):
                if not (gr.corner[e] or gr.wall[e]):
                    ends.append((gid, e, gr.P0 + gr.d * (gr.lo if e == 0 else gr.hi)))
        grid = collections.defaultdict(list)
        for k, (_g, _e, p) in enumerate(ends):
            grid[tuple(np.floor(p / 2).astype(int))].append(k)
        seen = set()
        for k, (_g, _e, p) in enumerate(ends):
            if k in seen:
                continue
            c0 = np.floor(p / 2).astype(int)
            near = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                    for j in grid.get((c0[0] + dx, c0[1] + dy, c0[2] + dz), []) if np.linalg.norm(ends[j][2] - p) < 0.75]
            seen.update(near)
            if len(near) != 2 or ends[near[0]][0] == ends[near[1]][0]:
                continue
            (g1, e1, p1), (g2, e2, p2) = ends[near[0]], ends[near[1]]
            r1, r2 = self.groups[g1], self.groups[g2]
            common = set(r1.pk) & set(r2.pk)
            self.stats["mitre_cand"] += 1
            if len(common) != 1:
                self.stats["mitre_rej_planes"] += 1
                continue
            P = next(iter(common))
            if abs(r1.r - r2.r) > 1e-6 or abs(float(r1.nA @ r1.nB) - float(r2.nA @ r2.nB)) > 1e-3:
                self.stats["mitre_rej_radius_angle"] += 1
                continue
            u1 = r1.d if e1 == 0 else -r1.d
            u2 = r2.d if e2 == 0 else -r2.d
            w1 = r1.wA if r1.pk[0] == P else r1.wB
            w2 = r2.wA if r2.pk[0] == P else r2.wB
            if abs(float(u1 @ u2)) > 0.02 or float(-u1 @ w2) < 0.98 or float(-u2 @ w1) < 0.98:
                self.stats["mitre_rej_not_reflex_L"] += 1
                continue
            sh = {}
            V = 0.5 * (p1 + p2)
            nPi = unit(u2 - u1)
            r1.mitre[e1] = dict(partner=(g2, e2), P=P, V=V, nPi=nPi, shared=sh, canon=False)
            r2.mitre[e2] = dict(partner=(g1, e1), P=P, V=V, nPi=nPi, shared=sh, canon=False)
            for gr_, e_ in ((r1, e1), (r2, e2)):
                self.extend_store(gr_, e_)
            self.mitres.append((g1, e1, g2, e2))
            self.stats["mitres_found"] += 1
        for gid in order:
            self.layout(self.groups[gid])

    def revert_broken_mitres(self):
        for g1, e1, g2, e2 in self.mitres:
            a_, b_ = self.groups[g1], self.groups[g2]
            if a_.ok and b_.ok:
                continue
            for gr, e in ((a_, e1), (b_, e2)):
                if gr.mitre[e] is not None:
                    self.drop_ext(gr, e)
            self.stats["mitres_reverted_partner"] += 1

    # --- 5c. wall ends: a run that butts into a wall keeps the full radius up to the wall and a cap fills the notch
    def find_wall_ends(self, order):
        """A run end (not part of a box corner) whose vertex lies on the plane of another face W, with the run heading away
        from W (u . n_W >= --wall-dot) and W having a boundary along both faces of the run (the hole the ledge leaves in the
        wall), is not tapered: gr.wall[e] = True. Anything else keeps the taper."""
        self.wall_log = []
        self.wall_why = {}  # (group, end) -> why an end was not made a wall end
        if not self.a.wall_ends:
            return
        a = self.a
        fl = [f for f in self.faces.values() if not f.bad]
        FN, FD = np.array([f.n for f in fl]), np.array([f.d for f in fl])
        FS = np.array([f.si for f in fl])
        byface = collections.defaultdict(list)
        for k, si in enumerate(self.E["f"]):
            byface[int(si)].append(k)

        def near_edge(pt, P0s, P1s):
            ab = P1s - P0s
            tt = np.clip(((pt - P0s) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-12), 0.0, 1.0)
            return float(np.linalg.norm(P0s + tt[:, None] * ab - pt, axis=1).min())

        for gid in order:
            gr = self.groups[gid]
            for e in (0, 1):
                if gr.corner[e]:
                    continue
                t = gr.lo if e == 0 else gr.hi
                u = gr.d if e == 0 else -gr.d
                p = gr.P0 + gr.d * t
                m = (FN @ u >= a.wall_dot) & (np.abs(FN @ p - FD) < 0.3)
                if not m.any():
                    self.stats["wall_rej_no_plane"] += 1
                    self.wall_why[(gid, e)] = "no_plane"
                    continue
                idx = [k for si in FS[m] for k in byface[int(si)]]
                if not idx:
                    self.stats["wall_rej_no_hole"] += 1
                    continue
                # the notch between the original edge corner and the arc: samples along the corner's diagonal
                wf = [self.faces[int(si)] for si in FS[m]]
                diag = (gr.wA + gr.wB) * gr.r
                cov = [any(self.point_in_face(f, p + diag * k) for f in wf) for k in (0.08, 0.2)]
                if all(cov):
                    gr.wall_cap[e] = False  # the wall face is drawn under the ledge: it already fills the notch
                    self.stats["wall_ends_under"] += 1
                else:
                    P0s, P1s = self.E["p0"][idx], self.E["p1"][idx]
                    ok = not any(cov) and near_edge(p, P0s, P1s) < 0.25
                    for w in (gr.wA, gr.wB):
                        for fr in (0.5, 1.0):
                            ok = ok and near_edge(p + w * gr.r * fr, P0s, P1s) < 0.25
                    if not ok:
                        self.stats["wall_rej_no_hole"] += 1
                        self.wall_why[(gid, e)] = "no_hole"
                        self.wall_log.append(("wall_rej", p))
                        continue
                gr.wall[e] = True
                gr.wall_pl[e] = (FN[m][int(np.argmax(FN[m] @ u))], float(FD[m][int(np.argmax(FN[m] @ u))]))
                self.stats["wall_ends"] += 1
                self.wall_log.append(("wall", p))
        for gid in order:
            self.layout(self.groups[gid])

    @staticmethod
    def point_in_face(f, pt, tol=0.1):
        """Is pt (projected on the plane of face f) inside one of its triangles (tolerance tol units)?"""
        X = f.A[:, :3]
        T = np.stack([X @ f.u, X @ f.v], axis=1)[f.tris]
        e1, e2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
        det = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
        dp = np.array([pt @ f.u, pt @ f.v]) - T[:, 0]
        with np.errstate(all="ignore"):
            a_ = (dp[:, 0] * e2[:, 1] - dp[:, 1] * e2[:, 0]) / det
            b_ = (e1[:, 0] * dp[:, 1] - e1[:, 1] * dp[:, 0]) / det
            e = tol / np.maximum(np.sqrt(np.abs(det)), 1e-6)
            return bool(((a_ >= -e) & (b_ >= -e) & (a_ + b_ <= 1 + 2 * e) & (np.abs(det) > 1e-9)).any())

    def build_wall_cap(self, gr, e):
        """Fan of triangles in the wall plane from the original edge corner E over the strip's end row (the notch the rounded
        arc leaves against the wall). Positions are the strip row's, so the cap is watertight with the strip."""
        t, _c, pts, _nms = gr.row_first if e == 0 else gr.row_last
        nW, dW = gr.wall_pl[e]
        E = gr.P0 + gr.d * ((dW - float(nW @ gr.P0)) / float(nW @ gr.d))  # edge line meets the wall plane
        best, bd = None, 1e18
        for sid in gr.fA:
            f = self.faces[sid]
            dd = float(np.linalg.norm(f.A[:, :3] - E, axis=1).min())
            if dd < bd:
                best, bd = f, dd
        f = best
        cache = {}

        def vert(x):
            key = tuple(np.round(x, 5))
            v = cache.get(key)
            if v is None:
                st, lm = f.eval_map(x - (float(x @ f.n) - f.d) * f.n)
                v = np.concatenate([x, st, lm, nW, f.nearest_color(x)])
                cache[key] = v
            return v

        ph = sorted(pts)
        vE = vert(E)
        for k in range(len(ph) - 1):
            T = np.array([vE, vert(pts[ph[k]]), vert(pts[ph[k + 1]])])
            cr = np.cross(T[1, :3] - T[0, :3], T[2, :3] - T[0, :3])
            if np.linalg.norm(cr) < 1e-6:
                continue
            if f.winding * float(cr @ T[:, 7:10].sum(0)) < 0:
                T = T[[0, 2, 1]]
            f.strip.append(T)
            self.stats["wall_cap_tris"] += 1
        self.cap_edges.append((E, pts[ph[0]]))
        self.cap_edges.append((E, pts[ph[-1]]))
        self.stats["wall_caps"] += 1

    def build_corner(self, cr):
        """Spherical-triangle patch closing a box corner: its boundary is the three strip end arcs, the interior a ring and a
        centre point on the sphere through them (normals radial). Each triangle goes to the face whose plane is nearest."""
        arcs = []
        for gid, e in cr["ends"]:
            gr = self.groups[gid]
            _t, _c, pts, nms = gr.row_first if e == 0 else gr.row_last
            ph = sorted(pts)
            arcs.append([gr.pk[0], gr.pk[1], [(pts[x], nms[x]) for x in ph], gr])
        first = arcs.pop(0)
        loop, cur = list(first[2]), first[1]
        while arcs:
            k = next(i for i, ar in enumerate(arcs) if cur in ar[:2])
            ar = arcs.pop(k)
            seq = ar[2] if ar[0] == cur else ar[2][::-1]
            loop.extend(seq[1:])
            cur = ar[1] if ar[0] == cur else ar[0]
        loop = loop[:-1]  # the last point repeats the first
        X = np.array([p for p, _n in loop])
        Nn = np.array([n for _p, n in loop])
        R = float(np.mean([self.groups[g].r * self.groups[g].R_over_c for g, _e in cr["ends"]]))
        K0 = (X - R * Nn).mean(0)
        u0 = unit(sum(self.groups[g].nA + self.groups[g].nB for g, _e in cr["ends"]))
        m = len(loop)
        ring = [K0 + R * unit(0.5 * Nn[i] + 0.5 * u0) for i in range(m)]
        rn = [unit(0.5 * Nn[i] + 0.5 * u0) for i in range(m)]
        ctr = K0 + R * u0
        # faces of the three planes: the one nearest to the corner
        pf = {}
        for gid, _e in cr["ends"]:
            gr = self.groups[gid]
            for pid, store in ((gr.pk[0], gr.fA), (gr.pk[1], gr.fB)):
                for sid in store:
                    f = self.faces[sid]
                    dd = float(np.linalg.norm(f.A[:, :3] - cr["pos"], axis=1).min())
                    if pid not in pf or dd < pf[pid][0]:
                        pf[pid] = (dd, f)
        cache = {}

        def vert(f, x, n):
            key = (f.si, tuple(np.round(x, 5)))
            v = cache.get(key)
            if v is None:
                st, lm = f.eval_map(x - (float(x @ f.n) - f.d) * f.n)
                v = np.concatenate([x, st, lm, n, f.nearest_color(x)])
                cache[key] = v
            return v

        tris = []
        for i in range(m):
            j = (i + 1) % m
            tris.append(((X[i], Nn[i]), (X[j], Nn[j]), (ring[j], rn[j])))
            tris.append(((X[i], Nn[i]), (ring[j], rn[j]), (ring[i], rn[i])))
            tris.append(((ring[i], rn[i]), (ring[j], rn[j]), (ctr, u0)))
        for tri in tris:
            g = sum(p for p, _n in tri) / 3
            pid = min(pf, key=lambda q: abs(float(self._pn(cr, q) @ g) - self._pd(cr, q)))
            f = pf[pid][1]
            T = np.array([vert(f, p, n) for p, n in tri])
            cr_ = np.cross(T[1, :3] - T[0, :3], T[2, :3] - T[0, :3])
            if np.linalg.norm(cr_) < 1e-6:
                continue
            if f.winding * float(cr_ @ T[:, 7:10].sum(0)) < 0:
                T = T[[0, 2, 1]]
            f.strip.append(T)
            self.stats["corner_patch_tris"] += 1
        self.stats["corner_patches"] += 1

    def _pn(self, cr, pid):
        for gid, _e in cr["ends"]:
            gr = self.groups[gid]
            if gr.pk[0] == pid:
                return gr.nA
            if gr.pk[1] == pid:
                return gr.nB

    def _pd(self, cr, pid):
        for gid, _e in cr["ends"]:
            gr = self.groups[gid]
            for k, store in ((0, gr.fA), (1, gr.fB)):
                if gr.pk[k] == pid:
                    return next(self.faces[s].d for s in store)

    def run(self):
        self.candidates()
        self.boundary_edges()
        self.match_edges()
        self.build_groups()
        used = 0
        order = []
        for gid, gr in enumerate(self.groups):
            why = self.prepare(gr)
            gr.ok = why is None
            if why:
                self.stats[why] += 1
            else:
                order.append(gid)
        self.find_corners(order)
        self.find_wall_ends(order)
        self.find_mitres(order)
        self.drop_overlapping(order)
        self.revert_broken_corners()
        self.revert_broken_mitres()
        if self.a.uv_mode == "align":
            self.align_textures()
        self.end_log = []  # (kind, position) of every end of an accepted run: corner / wall / taper
        for gid, gr in enumerate(self.groups):
            if gr.ok:
                for e in (0, 1):
                    kind = "corner" if gr.corner[e] else ("mitre" if gr.mitre[e] is not None else "wall" if gr.wall[e] else "taper:" + self.wall_why.get((gid, e), "reverted"))
                    self.end_log.append((kind, gr.P0 + gr.d * (gr.lo if e == 0 else gr.hi)))
        for gid, gr in enumerate(self.groups):
            if gr.ok:
                for s in gr.fA:
                    self.cut_face(self.faces[s], gr, gr.wA, gid, 0)
                for s in gr.fB:
                    self.cut_face(self.faces[s], gr, gr.wB, gid, 1)
        self.rebuild_cutverts()
        for gid, gr in enumerate(self.groups):
            if not gr.ok:
                continue
            n = self.build_strip(gr, gid)
            self.stats["strip_tris"] += n
            self.stats["groups_bevelled"] += 1
            self.stats["bevelled_length"] += gr.hi - gr.lo
            if gr.r < self.a.radius - 1e-9:
                self.stats["groups_adaptive_radius"] += 1
            used += 1
        for cr in self.corners:
            self.build_corner(cr)
        for gid, gr in enumerate(self.groups):
            if gr.ok:
                for e in (0, 1):
                    if gr.wall[e] and gr.wall_cap[e]:
                        self.build_wall_cap(gr, e)
                    elif gr.wall[e]:  # end row lies inside the wall face drawn under the ledge: not a crack
                        pts = (gr.row_first if e == 0 else gr.row_last)[2]
                        ph = sorted(pts)
                        self.cap_edges.extend((pts[ph[k]], pts[ph[k + 1]]) for k in range(len(ph) - 1))
        self.stats["rej_total_groups"] = self.stats["groups_candidate"] - used
        return self.assemble()

    def align_textures(self):
        """Shift the st of whole coplanar-connected face components so the texture continues across bevelled edges.

        Greedy spanning forest over components, longest runs first: the first component stays, each further one is
        shifted by the non-integer part of the st mismatch measured on the run (integer shifts are invisible on a tiling
        texture). Pairs with other shaders, different scale or a mapping that drifts along the edge are skipped."""
        par = {}

        def find(x):
            while par.setdefault(x, x) != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        for a_, b_ in self.coplanar_pairs:
            if self.faces[a_].surf["shader"] == self.faces[b_].surf["shader"]:
                par[find(a_)] = find(b_)
        members = collections.defaultdict(list)
        for si in self.faces:
            members[find(si)].append(si)
        fixed, st = set(), self.stats

        def shift(c, off):
            for si in members[c]:
                f = self.faces[si]
                f.A[:, 3:5] += off
                f.fit[2, :2] += off
        runs = sorted((g for g in self.groups if g.ok), key=lambda g: -(g.hi - g.lo))
        for gr in runs:
            fa, fb = self.faces[next(iter(gr.fA))], self.faces[next(iter(gr.fB))]
            ca, cb = find(fa.si), find(fb.si)
            if ca == cb or (ca in fixed and cb in fixed):
                continue
            if fa.surf["shader"] != fb.surf["shader"]:
                st["align_other_shader"] += 1
                continue
            ga = math.sqrt(abs(np.linalg.det(fa.fit[:2, :2])))
            gb = math.sqrt(abs(np.linalg.det(fb.fit[:2, :2])))
            if min(ga, gb) < 1e-9 or max(ga, gb) / min(ga, gb) > 1.5:
                st["align_scale"] += 1
                continue
            res = []
            th = math.acos(max(-1.0, min(1.0, float(fa.n @ fb.n))))
            half = gr.r * (th / 2) / math.tan(th / 2) if th > 1e-3 else gr.r
            ins = []
            for f_ in (fa, fb):
                w = np.cross(f_.n, gr.d)
                w /= np.linalg.norm(w)
                if float((f_.centroid - gr.P0) @ w) < 0:
                    w = -w
                ins.append((gr.r - half) * w)
            for tf in (0.2, 0.5, 0.8):
                pm = gr.P0 + gr.d * (gr.lo + tf * (gr.hi - gr.lo))
                res.append(fa.eval_map(pm + ins[0])[0] - fb.eval_map(pm + ins[1])[0])
            res = np.array(res)
            if ca in fixed:
                mov, ref, sgn = cb, ca, 1.0
            elif cb in fixed:
                mov, ref, sgn = ca, cb, -1.0
            else:
                fixed.add(ca)
                mov, ref, sgn = cb, ca, 1.0
            d = res[1]
            off = d - np.rint(d)
            if np.abs((res - res[1]) - np.rint(res - res[1])).max() > 0.15:
                st["align_drift"] += 1
                continue
            shift(mov, sgn * off)
            fixed.add(mov)
            st["align_shifted"] += 1
            st["align_shift_sum"] += float(np.abs(off).max())
            st["align_faces"] += len(members[mov])

    def drop_overlapping(self, order):
        """Reject runs whose cut region (trapezoid on the face) overlaps another accepted run's on the same face:
        sequential clipping there leaves cracks. Longer runs win."""
        placed = collections.defaultdict(list)  # face -> list of 2D convex polygons

        def mext(gr, w):
            """Extension of the cut past each run end on this side (mitre ends, on the shared plane only)."""
            side = 0 if w is gr.wA else 1
            return [gr.r if gr.mitre[e] is not None and gr.mitre[e]["P"] == gr.pk[side] else 0.0 for e in (0, 1)]

        def region(gr, f, w):
            r, tap = gr.r, gr.tap
            x0, x1 = mext(gr, w)
            lo0 = [(gr.te_lo, 0.0), (gr.te_lo, r)] if gr.corner[0] or gr.wall[0] else [(gr.lo, 0.0), (gr.lo + tap, r)]
            hi0 = [(gr.te_hi, 0.0), (gr.te_hi, r)] if gr.corner[1] or gr.wall[1] else [(gr.hi, 0.0), (gr.hi - tap, r)]
            if gr.mitre[0] is not None:
                lo0 = [(gr.lo - x0, 0.0), (gr.lo - x0, r)]
            if gr.mitre[1] is not None:
                hi0 = [(gr.hi + x1, 0.0), (gr.hi + x1, r)]
            pts = [lo0[0], hi0[0], hi0[1], lo0[1]]
            P = np.array([gr.P0 + gr.d * t + w * s_ for t, s_ in pts])
            return np.stack([P @ f.u, P @ f.v], axis=1)

        def overlap(A, B):
            for poly in (A, B):
                for i in range(len(poly)):
                    e = poly[(i + 1) % len(poly)] - poly[i]
                    nrm = np.array([-e[1], e[0]])
                    nl = np.linalg.norm(nrm)
                    if nl < 1e-9:
                        continue
                    nrm /= nl
                    a0, a1 = (A @ nrm).min(), (A @ nrm).max()
                    b0, b1 = (B @ nrm).min(), (B @ nrm).max()
                    if min(a1, b1) - max(a0, b0) < 0.05:
                        return False
            return True

        def covered(gr, store, w):
            """Sample points of the cut region must lie inside the faces of that side (else the strip would overhang)."""
            r = gr.r
            tl = 0.0 if gr.corner[0] or gr.wall[0] or gr.mitre[0] is not None else gr.tap
            th = 0.0 if gr.corner[1] or gr.wall[1] or gr.mitre[1] is not None else gr.tap
            e = min(0.3, 0.25 * (gr.te_hi - gr.te_lo))
            q = [(gr.te_lo + e, 0.1), (gr.te_hi - e, 0.1), (gr.te_lo + max(tl, e), r - 0.1), (gr.te_hi - max(th, e), r - 0.1),
                 (0.5 * (gr.lo + gr.hi), 0.1), (0.5 * (gr.lo + gr.hi), r - 0.1),
                 (gr.te_lo + max(0.5 * tl, e), 0.5 * r), (gr.te_hi - max(0.5 * th, e), 0.5 * r)]
            x0, x1 = mext(gr, w)
            if x0 > 0:
                q += [(gr.lo - 0.5 * x0, 0.1), (gr.lo - 0.5 * x0, r - 0.1), (gr.lo - x0 + 0.2, 0.2), (gr.lo - x0 + 0.2, r - 0.1)]
            if x1 > 0:
                q += [(gr.hi + 0.5 * x1, 0.1), (gr.hi + 0.5 * x1, r - 0.1), (gr.hi + x1 - 0.2, 0.2), (gr.hi + x1 - 0.2, r - 0.1)]
            pts = np.array([gr.P0 + gr.d * t + w * s_ for t, s_ in q])
            tol = 0.1
            for pt in pts:
                ok = False
                for sid in store:
                    f = self.faces[sid]
                    X = f.A[:, :3]
                    p2 = np.array([pt @ f.u, pt @ f.v])
                    T = np.stack([X @ f.u, X @ f.v], axis=1)[f.tris]  # (nt,3,2)
                    e1, e2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
                    det = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
                    dp = p2 - T[:, 0]
                    with np.errstate(all="ignore"):
                        a_ = (dp[:, 0] * e2[:, 1] - dp[:, 1] * e2[:, 0]) / det
                        b_ = (e1[:, 0] * dp[:, 1] - e1[:, 1] * dp[:, 0]) / det
                    e = tol / np.maximum(np.sqrt(np.abs(det)), 1e-6)
                    with np.errstate(all="ignore"):
                        hit = ((a_ >= -e) & (b_ >= -e) & (a_ + b_ <= 1 + 2 * e) & (np.abs(det) > 1e-9)).any()
                    if hit:
                        ok = True
                        break
                if not ok:
                    return False
            return True

        for gid in sorted(order, key=lambda g: -(self.groups[g].hi - self.groups[g].lo)):
            gr = self.groups[gid]
            for e in (0, 1):  # a mitre needs both runs: a partner that was rejected before leaves this end tapered
                if gr.mitre[e] is not None and not self.groups[gr.mitre[e]["partner"][0]].ok:
                    self.clear_mitre(gr, e)
            for attempt in (0, 1):  # attempt 1: the run again with its wall and mitre ends tapered
                bad = None
                partners = {m["partner"][0] for m in gr.mitre if m is not None}
                if not (covered(gr, gr.fA, gr.wA) and covered(gr, gr.fB, gr.wB)):
                    bad = "rej_face_coverage"
                else:
                    mine = [(s, region(gr, self.faces[s], gr.wA)) for s in gr.fA] + [(s, region(gr, self.faces[s], gr.wB)) for s in gr.fB]
                    if any(overlap(poly, q) for s, poly in mine for q, g2 in placed[s] if g2 not in partners):
                        bad = "rej_overlap_run"
                if bad and attempt == 0 and partners:
                    self.stats["mitre_fail_" + bad] += 1
                if bad is None or attempt == 1 or not (any(gr.wall) or partners):
                    break
                gr.wall = [False, False]
                for e in (0, 1):
                    if gr.mitre[e] is not None:
                        self.clear_mitre(gr, e)
                        self.stats["mitres_reverted_overlap"] += 1
                self.layout(gr)
                self.stats["wall_ends_reverted_overlap"] += 1
            if bad:
                gr.ok = False
                self.stats[bad] += 1
                continue
            for s, poly in mine:
                placed[s].append((poly, gid))

    # --- 6. rebuild lumps
    def assemble(self):
        bsp, a = self.bsp, self.a
        V0, I0, S0 = bsp.verts, bsp.indexes, bsp.surfaces
        S = S0.copy()
        mods = {}
        modified = [f for f in self.faces.values() if f.polys is not None]
        for f in sorted(modified, key=lambda f: f.si):
            tris = []
            polys = merge_convex(f.polys, f.n * f.winding) if a.merge_polys else f.polys
            self.stats["face_polys_before_merge"] += len(f.polys)
            self.stats["face_polys_after_merge"] += len(polys)
            for P in polys:
                tris.extend(triangulate(P))
            if polys is not f.polys:
                nn = f.n * f.winding
                if any(float(np.cross(T[1, :3] - T[0, :3], T[2, :3] - T[0, :3]) @ nn) < 1e-3 for T in tris):
                    polys, tris = f.polys, []
                    for P in polys:
                        tris.extend(triangulate(P))
            self.stats["face_tris"] += len(tris)
            self.stats["face_poly_verts"] += sum(len(P) for P in polys)
            def quant(T):
                Q = T.astype(np.float32)
                Q[:, 10:14] = np.clip(np.rint(T[:, 10:14]), 0, 255)
                return Q

            def good(Q):
                x = Q[:, :3].astype(np.float64)
                return np.linalg.norm(np.cross(x[1] - x[0], x[2] - x[0])) >= 1e-4

            qc = [quant(T) for T in tris]
            qs = [quant(T) for T in f.strip]
            kc, ks = [Q for Q in qc if good(Q)], [Q for Q in qs if good(Q)]
            self.stats["tris_dropped_sliver"] += len(qc) + len(qs) - len(kc) - len(ks)
            vmap, vrows, idx = {}, [], []
            for Q in kc + ks:
                for q in Q:
                    key = q.tobytes()
                    k = vmap.get(key)
                    if k is None:
                        k = vmap[key] = len(vrows)
                        vrows.append(q)
                    idx.append(k)
            if not vrows:
                self.stats["faces_emptied_kept_stock"] += 1
                continue
            if a.surface_type == "face" and len(vrows) > MAX_BEVEL_FACE_VERTS:
                self.stats["faces_reverted_over_vert_limit"] += 1
                continue
            self.tagged.append((f.si, len(kc), len(ks)))
            arr = np.zeros(len(vrows), dtype=DRAWVERT)
            R = np.array(vrows)
            arr["xyz"], arr["st"], arr["lm"], arr["n"] = R[:, 0:3], R[:, 3:5], R[:, 5:7], R[:, 7:10]
            arr["c"] = R[:, 10:14].astype(np.uint8)
            s = S[f.si]
            self.stats["verts_orphaned"] += int(s["nv"])
            want_tri = a.surface_type == "tri"
            mods[f.si] = (arr, np.array(idx, dtype="<i4"))
            if want_tri:
                s["type"] = MST_TRISOUP
                self.stats["surfaces_converted_to_trisoup"] += 1
            else:
                self.stats["surfaces_kept_planar"] += 1
            self.stats["surfaces_modified"] += 1
        # lay the vertex/index lumps out again: every surface's own range in surface order. The stock ranges of the rewritten
        # surfaces are dropped (nothing else references them), so the lumps hold exactly what is drawn.
        newv, newi, nv, ni = [], [], 0, 0
        for si in range(len(S)):
            s = S[si]
            if si in mods:
                av, ai = mods[si]
            else:
                av, ai = V0[s["fv"]:s["fv"] + s["nv"]], I0[s["fi"]:s["fi"] + s["ni"]]
            s["fv"], s["nv"], s["fi"], s["ni"] = nv, len(av), ni, len(ai)
            newv.append(av)
            newi.append(ai)
            nv += len(av)
            ni += len(ai)
        self.stats["verts_before"], self.stats["verts_after"] = len(V0), nv
        self.stats["indexes_before"], self.stats["indexes_after"] = len(I0), ni
        out = Bsp(bsp.write())
        out.lumps[L_VERT] = np.concatenate(newv).tobytes()
        out.lumps[L_INDEX] = np.concatenate(newi).tobytes()
        out.lumps[L_SURF] = S.tobytes()
        return out


# ------------------------------------------------------------------------------------------------ baked models
DEFAULT_SMOOTH = r"^models[/\\](?!players)|textures/(props|metal_misc|wood|chat)/"


def smooth_trisoup(bsp, pattern, crease=90.0, quiet=False):
    """Loop-subdivide (one level, normal displacement only, see tools/model-smooth/mdc_smooth.py) the trisoup surfaces
    (baked misc_models: torches, cage lights, furniture ...) whose shader matches PATTERN. Returns a new Bsp."""
    sys.path.insert(0, str(ROOT / "tools/model-smooth"))
    import mdc_smooth as ms
    ms.Opts.crease_angle = crease
    rx = re.compile(pattern)
    V0, I0, S = bsp.verts, bsp.indexes, bsp.surfaces.copy()
    names = bsp.shader_names()
    newv, newi, nv, ni = [], [], 0, 0
    st = collections.Counter()
    for si in range(len(S)):
        s = S[si]
        av, ai = V0[s["fv"]:s["fv"] + s["nv"]], I0[s["fi"]:s["fi"] + s["ni"]]
        if s["type"] == MST_TRISOUP and rx.search(names[s["shader"]]) and len(ai) >= 24:
            o = type("Surf", (), {})()
            o.P, o.N = av["xyz"].astype(np.float64)[None], av["n"].astype(np.float64)[None]
            o.tris, o.st = ai.reshape(-1, 3).astype(np.int64), av["st"].astype(np.float64)
            res, info = ms.smooth_surface(o, ms.Opts)
            if res is None:
                st["skipped: " + (info["reason"].split(" (")[0] or "?")] += 1
            else:
                Pn, Nn, uvn, ot = res
                pv = info["pv"]
                n0 = len(av)
                bv = np.zeros(len(Pn[0]), dtype=DRAWVERT)
                bv[:n0] = av
                bv["xyz"] = Pn[0]
                bv["n"] = Nn[0]
                bv["st"] = uvn
                if len(pv):
                    for fld in ("lm",):
                        bv[fld][n0:] = (av[fld][pv[:, 0]] + av[fld][pv[:, 1]]) * 0.5
                    bv["c"][n0:] = ((av["c"][pv[:, 0]].astype(np.int32) + av["c"][pv[:, 1]]) // 2).astype(np.uint8)
                av, ai = bv, ot.reshape(-1).astype("<i4")
                st["smoothed"] += 1
                st["tris_before"] += info["before_t"]
                st["tris_after"] += info["after_t"]
        s["fv"], s["nv"], s["fi"], s["ni"] = nv, len(av), ni, len(ai)
        newv.append(av)
        newi.append(ai)
        nv += len(av)
        ni += len(ai)
    if not quiet:
        print("baked models:", dict(st))
    out = Bsp(bsp.write())
    out.lumps[L_VERT] = np.concatenate(newv).tobytes()
    out.lumps[L_INDEX] = np.concatenate(newi).tobytes()
    out.lumps[L_SURF] = S.tobytes()
    return out


DEFAULT_BRUSH_PROPS = r"textures/(props|metal_misc|wood|town_wood|chat)/"


def smooth_brush_props(bsp, pattern=DEFAULT_BRUSH_PROPS, max_extent=100.0, min_faces=6, crease=90.0, quiet=False):
    """Props built from brushes (torches, brackets, small crates) are plain type 1 faces of the world model. Welded by
    position, the faces of one prop (shader matching PATTERN, whole group at most MAX_EXTENT units) form one small mesh;
    that mesh is Loop-smoothed together and the result is split back to the stock surfaces, so surface count, shaders and
    lightmap pages are unchanged. Open (hidden) sides stay pinned. Returns a new Bsp."""
    sys.path.insert(0, str(ROOT / "tools/model-smooth"))
    import mdc_smooth as ms
    ms.Opts.crease_angle = crease
    rx = re.compile(pattern)
    V0, I0, S = bsp.verts, bsp.indexes, bsp.surfaces.copy()
    names = bsp.shader_names()
    m0 = bsp.models[0]
    cand = [si for si in range(int(m0["fs"]), int(m0["fs"] + m0["ns"]))
            if S[si]["type"] == MST_PLANAR and S[si]["fog"] <= 0 and rx.search(names[S[si]["shader"]])]
    par = {si: si for si in cand}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    owner = {}
    for si in cand:
        s = S[si]
        for x in np.rint(V0["xyz"][s["fv"]:s["fv"] + s["nv"]].astype(np.float64) * 8).astype(np.int64):
            k = x.tobytes()
            if k in owner:
                par[find(si)] = find(owner[k])
            else:
                owner[k] = si
    comps = collections.defaultdict(list)
    for si in cand:
        comps[find(si)].append(si)
    mods, st = {}, collections.Counter()
    for sis in comps.values():
        sis.sort()
        X = np.concatenate([V0["xyz"][S[i]["fv"]:S[i]["fv"] + S[i]["nv"]] for i in sis])
        if len(sis) < min_faces or float((X.max(0) - X.min(0)).max()) > max_extent:
            st["components skipped"] += 1
            continue
        verts, tris, tsurf, base = [], [], [], 0
        for i in sis:
            s = S[i]
            av, ai = V0[s["fv"]:s["fv"] + s["nv"]], I0[s["fi"]:s["fi"] + s["ni"]].reshape(-1, 3)
            verts.append(av)
            tris.append(ai + base)
            tsurf += [i] * len(ai)
            base += len(av)
        av, tr, tsurf = np.concatenate(verts), np.concatenate(tris).astype(np.int64), np.array(tsurf)
        o = type("Surf", (), {})()
        o.P, o.N, o.tris, o.st = av["xyz"].astype(np.float64)[None], av["n"].astype(np.float64)[None], tr, av["st"].astype(np.float64)
        res, info = ms.smooth_surface(o, ms.Opts)
        if res is None:
            st["components too big"] += 1
            continue
        Pn, Nn, uvn, ot = res
        pv, n0 = info["pv"], len(av)
        bv = np.zeros(len(Pn[0]), dtype=DRAWVERT)
        bv[:n0] = av
        bv["xyz"], bv["n"], bv["st"] = Pn[0], Nn[0], uvn
        if len(pv):
            bv["lm"][n0:] = (av["lm"][pv[:, 0]] + av["lm"][pv[:, 1]]) * 0.5
            bv["c"][n0:] = ((av["c"][pv[:, 0]].astype(np.int32) + av["c"][pv[:, 1]]) // 2).astype(np.uint8)
        ot = ot.reshape(-1, 3)
        ok = True
        out = {}
        for i in sis:
            sel = ot[np.repeat(tsurf == i, 4)]
            used, inv = np.unique(sel, return_inverse=True)
            if len(used) > MAX_BEVEL_FACE_VERTS:
                ok = False
                break
            out[i] = (bv[used], inv.reshape(-1).astype("<i4"))
        if not ok:
            st["components over vertex limit"] += 1
            continue
        mods.update(out)
        st["components smoothed"] += 1
        st["surfaces"] += len(sis)
    newv, newi, nv, ni = [], [], 0, 0
    for si in range(len(S)):
        s = S[si]
        av, ai = mods.get(si, (V0[s["fv"]:s["fv"] + s["nv"]], I0[s["fi"]:s["fi"] + s["ni"]]))
        s["fv"], s["nv"], s["fi"], s["ni"] = nv, len(av), ni, len(ai)
        newv.append(av)
        newi.append(ai)
        nv += len(av)
        ni += len(ai)
    if not quiet:
        print("brush props:", dict(st))
    res = Bsp(bsp.write())
    res.lumps[L_VERT] = np.concatenate(newv).tobytes()
    res.lumps[L_INDEX] = np.concatenate(newi).tobytes()
    res.lumps[L_SURF] = S.tobytes()
    return res


# ------------------------------------------------------------------------------------------------ validation
def validate(orig, new, bv):
    """Checks on the modified BSP. Returns list of (name, ok, detail)."""
    res = []
    V, I, S = new.verts, new.indexes, new.surfaces
    S0 = orig.surfaces
    ok_idx = True
    bad_range = 0
    for i in range(len(S)):
        s = S[i]
        if s["type"] in (MST_PLANAR, MST_TRISOUP):
            ix = I[s["fi"]:s["fi"] + s["ni"]]
            if len(ix) and (ix.min() < 0 or ix.max() >= s["nv"]) or s["fv"] + s["nv"] > len(V) or s["fi"] + s["ni"] > len(I) or s["ni"] % 3:
                bad_range += 1
        else:
            if s["fv"] + s["nv"] > len(V) or s["fi"] + s["ni"] > len(I):
                bad_range += 1
    res.append(("indices/vert ranges valid for all surfaces", bad_range == 0, f"{bad_range} bad"))
    res.append(("surface count unchanged", len(S) == len(S0), f"{len(S0)} -> {len(S)}"))
    nan = int(~np.isfinite(V["xyz"]).all() + ~np.isfinite(V["st"]).all() + ~np.isfinite(V["lm"]).all() + ~np.isfinite(V["n"]).all())
    res.append(("no NaN/inf in verts", nan == 0, ""))
    same = all(S[i][k] == S0[i][k] for i in range(len(S)) for k in ("shader", "fog", "lmn")) if len(S) < 0 else \
        bool((S["shader"] == S0["shader"]).all() and (S["fog"] == S0["fog"]).all() and (S["lmn"] == S0["lmn"]).all())
    res.append(("shader/fog/lightmapNum unchanged", same, ""))
    other = all(new.lumps[i] == orig.lumps[i] for i in range(NLUMPS) if i not in (L_VERT, L_INDEX, L_SURF))
    res.append(("all other lumps byte-identical", other, ""))
    # per modified surface checks
    degen = lm_out = nrm_bad = n_strip = 0
    lm_clamped_tol = 1e-6
    ties = 0
    mod = {si: (c, ns) for si, c, ns in bv.tagged}
    for si, (nclip, nstrip) in mod.items():
        s = S[si]
        v = V[s["fv"]:s["fv"] + s["nv"]]
        ix = I[s["fi"]:s["fi"] + s["ni"]].reshape(-1, 3)
        T = v["xyz"][ix].astype(np.float64)
        cr = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        degen += int((np.linalg.norm(cr, axis=1) < 1e-4).sum())
        if s["lmn"] >= 0:
            lo = np.array([s["lmx"], s["lmy"]]) / 128.0 - lm_clamped_tol
            hi = np.array([s["lmx"] + s["lmw"], s["lmy"] + s["lmh"]]) / 128.0 + lm_clamped_tol
            f = bv.faces[si]
            # only strip vertices are clamped; original vertices may sit on the rect by construction
            lm_out += int(((v["lm"] < lo) | (v["lm"] > hi)).any(1).sum())
        # strip triangles are the last nstrip triangles of the surface
        if nstrip:
            st = slice(len(ix) - nstrip, len(ix))
            navg = v["n"][ix[st]].astype(np.float64).sum(1)
            f = bv.faces[si]
            d = (cr[st] * navg).sum(1) * f.winding
            big = np.linalg.norm(cr[st], axis=1) > 0.05  # slivers below 0.05 unit^2 have no meaningful orientation
            nrm_bad += int(((d <= 0) & big).sum())
            n_strip += nstrip
        # winding of the clipped (non-strip) triangles must agree with the original orientation
        f = bv.faces[si]
        if nclip:
            g = (cr[:nclip] @ f.n) * f.winding
            ties += int(((g < -1e-6) & (np.linalg.norm(cr[:nclip], axis=1) > 0.05)).sum())
    res.append(("no degenerate triangles in modified surfaces", degen == 0, f"{degen} degenerate"))
    res.append(("lightmap coords inside each surface rect (+-1e-6)", lm_out == 0, f"{lm_out} verts outside"))
    res.append(("strip triangle normals agree with vertex normals", nrm_bad == 0, f"{nrm_bad}/{n_strip} flipped"))
    res.append(("clipped face triangles keep original winding", ties == 0, f"{ties} flipped"))
    # T-gaps: strip boundary edges vs clipped face edges (per surface group is not enough; strips border other
    # surfaces' cuts), so compare globally on quantised endpoints
    q = lambda p: tuple(np.round(np.asarray(p, dtype=np.float64) / 2e-3).astype(np.int64))
    strip_edges, face_edges = collections.Counter(), collections.Counter()
    face_segs = []
    for si, (nclip, nstrip) in mod.items():
        s = S[si]
        v = V[s["fv"]:s["fv"] + s["nv"]]["xyz"].astype(np.float64)
        ix = I[s["fi"]:s["fi"] + s["ni"]].reshape(-1, 3)
        for k, tri in enumerate(ix):
            tgt = strip_edges if k >= len(ix) - nstrip else face_edges
            for a_, b_ in ((0, 1), (1, 2), (2, 0)):
                pa, pb = v[tri[a_]], v[tri[b_]]
                if np.linalg.norm(pa - pb) < 1e-4:
                    continue
                ka, kb = q(pa), q(pb)
                tgt[(min(ka, kb), max(ka, kb))] += 1
                if tgt is face_edges:
                    face_segs.append((pa, pb))
    open_edges = [e for e, c in strip_edges.items() if c == 1]
    capq = set()
    for pa, pb in bv.cap_edges:  # cap edges along the boundary of the (unmodified) wall face: shared with it by construction
        ka, kb = q(np.float32(pa)), q(np.float32(pb))  # as stored in the lump (float32): quantisation ties must agree
        capq.add((min(ka, kb), max(ka, kb)))
    n_cap_open = sum(1 for e in open_edges if e in capq and e not in face_edges)
    open_edges = [e for e in open_edges if e not in capq or e in face_edges]
    exact = sum(1 for e in open_edges if e in face_edges)
    unmatched = [e for e in open_edges if e not in face_edges]
    # collinear partial match for the rest (T-junction on a face edge)
    CELL = 8.0
    grid = collections.defaultdict(list)
    for k, (pa, pb) in enumerate(face_segs):
        for c in {tuple(np.floor(((pa + (pb - pa) * u) / CELL)).astype(int)) for u in np.linspace(0, 1, max(2, int(np.linalg.norm(pb - pa) / 4) + 2))}:
            grid[c].append(k)
    partial = tiny = 0
    gaps = []
    for e in unmatched:
        pa, pb = np.array(e[0]) * 2e-3, np.array(e[1]) * 2e-3
        m = 0.5 * (pa + pb)
        c0 = np.floor(m / CELL).astype(int)
        cand = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    cand.update(grid.get((c0[0] + dx, c0[1] + dy, c0[2] + dz), ()))
        found = False
        for k in cand:
            a_, b_ = face_segs[k]
            ab = b_ - a_
            tt = min(1.0, max(0.0, float((m - a_) @ ab) / max(float(ab @ ab), 1e-12)))
            if np.linalg.norm(a_ + tt * ab - m) < 5e-3:
                found = True
                break
        if found:
            partial += 1
        elif np.linalg.norm(pb - pa) < 0.25:
            tiny += 1  # sub-quarter-unit slivers at taper ends where the real face edge deviates from the exact plane line
        else:
            gaps.append((pa, pb))
    res.append(("strip boundary edges shared with a clipped face edge",
                not gaps, f"{len(open_edges)} open strip edges: {exact} exact, {partial} collinear-partial (T-junction), {tiny} tiny (<0.25u) unmatched, {len(gaps)} longer unmatched; {n_cap_open} wall-end edges on/in a wall face excluded"))
    return res, gaps


# ------------------------------------------------------------------------------------------------ outputs
def world_tris(bsp, region=None):
    """(positions (T,3,3), normals (T,3,3), surface index (T), type) for planar+trisoup world surfaces."""
    V, I, S, m0 = bsp.verts, bsp.indexes, bsp.surfaces, bsp.models[0]
    P, N, SI = [], [], []
    for si in range(int(m0["fs"]), int(m0["fs"] + m0["ns"])):
        s = S[si]
        if s["type"] not in (MST_PLANAR, MST_TRISOUP):
            continue
        v = V[s["fv"]:s["fv"] + s["nv"]]
        ix = I[s["fi"]:s["fi"] + s["ni"]].reshape(-1, 3)
        T = v["xyz"][ix].astype(np.float64)
        if region is not None:
            lo, hi = np.array(region[:3]), np.array(region[3:])
            cen = T.mean(1)
            m = ((cen >= lo) & (cen <= hi)).all(1)  # triangles whose centroid is inside the box
            T, ix = T[m], ix[m]
        if len(T):
            P.append(T)
            N.append(v["n"][ix].astype(np.float64))
            SI.append(np.full(len(T), si))
    if not P:
        return np.zeros((0, 3, 3)), np.zeros((0, 3, 3)), np.zeros(0, dtype=int)
    return np.concatenate(P), np.concatenate(N), np.concatenate(SI)


def write_obj(path, bsp, region):
    P, N, SI = world_tris(bsp, region)
    with open(path, "w") as fh:
        fh.write(f"# {len(P)} triangles\n")
        for k, T in enumerate(P):
            for p in T:
                fh.write(f"v {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}\n")
        for k in range(len(P)):
            fh.write(f"f {3 * k + 1} {3 * k + 2} {3 * k + 3}\n")
    print(f"{path}: {len(P)} triangles")


def md4(data):
    """Pure-Python MD4 (hashlib's md4 is often missing); returns the 16 digest bytes."""
    M = 0xFFFFFFFF
    rol = lambda x, n: ((x << n) | (x >> (32 - n))) & M
    msg = bytearray(data) + b"\x80"
    msg += b"\0" * ((56 - len(msg)) % 64) + struct.pack("<Q", (len(data) * 8) & 0xFFFFFFFFFFFFFFFF)
    a0, b0, c0, d0 = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476
    for off in range(0, len(msg), 64):
        X = struct.unpack_from("<16I", msg, off)
        a, b, c, d = a0, b0, c0, d0
        for i in range(16):
            sh = (3, 7, 11, 19)[i % 4]
            t = (a + ((b & c) | (~b & d)) + X[i]) & M
            a, b, c, d = d, rol(t, sh), b, c
        for i in range(16):
            k = (i % 4) * 4 + i // 4
            sh = (3, 5, 9, 13)[i % 4]
            t = (a + ((b & c) | (b & d) | (c & d)) + X[k] + 0x5A827999) & M
            a, b, c, d = d, rol(t, sh), b, c
        for i in range(16):
            k = (0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15)[i]
            sh = (3, 9, 11, 15)[i % 4]
            t = (a + (b ^ c ^ d) + X[k] + 0x6ED9EBA1) & M
            a, b, c, d = d, rol(t, sh), b, c
        a0, b0, c0, d0 = (a0 + a) & M, (b0 + b) & M, (c0 + c) & M, (d0 + d) & M
    return struct.pack("<4I", a0, b0, c0, d0)


def block_checksum(data):
    """Com_BlockChecksum: the four LE words of the MD4 digest XORed together."""
    w = struct.unpack("<4I", md4(data))
    return w[0] ^ w[1] ^ w[2] ^ w[3]


def aas_checksum(aas):
    """Decoded bspchecksum field of an .aas file (bytes 8..12, obfuscated with (i*119)&0xff counted from byte 8)."""
    return struct.unpack("<I", bytes(aas[8 + i] ^ ((i * 119) & 0xFF) for i in range(4)))[0]


def patch_aas(aas, checksum):
    out = bytearray(aas)
    out[8:12] = bytes(b ^ ((i * 119) & 0xFF) for i, b in enumerate(struct.pack("<I", checksum)))
    return bytes(out)


def find_aas(name):
    """{maps/NAME*.aas: bytes} from the paks (later pak overrides the earlier)."""
    out = {}
    for p in sorted(glob.glob(PAK_GLOB)):
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if re.fullmatch(rf"maps/{re.escape(name)}(_b\d+)?\.aas", n):
                    out[n] = z.read(n)
    return out


def write_pk3(path, name, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    chk = block_checksum(data)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        zi = zipfile.ZipInfo(f"maps/{name}.bsp", date_time=(2020, 1, 1, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, data)
        # the AAS header must carry the checksum of the new BSP (the collision lumps are unchanged, so the AAS stays valid)
        for n, aas in sorted(find_aas(name).items()):
            zi = zipfile.ZipInfo(n, date_time=(2020, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, patch_aas(aas, chk))
            print(f"  {n}: bspchecksum {aas_checksum(aas):#010x} -> {chk:#010x}")
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def print_stats(bv):
    st = bv.stats
    rej = ["rej_coplanar", "rej_angle", "rej_concave"]
    grp = ["rej_short", "rej_thin_face", "rej_concave"]
    print("--- stats ---")
    print(f"candidate faces:                {st['surf_candidates']} (skipped: shader {st['surf_skipped_shader']}, "
          f"non-planar surfaces {st['surf_not_planar']}, bad face fit {st['surf_skipped_bad_face']})")
    print(f"boundary edges (1 tri in face): {st['boundary_edges']}")
    print(f"collinear overlapping pairs:    {st['edge_pairs_collinear_overlap']} (candidate edges)")
    print(f"  rejected coplanar:            {st['rej_coplanar']}")
    print(f"  rejected dihedral angle:      {st['rej_angle']}")
    print(f"  rejected concave:             {st['rej_concave']} (pair level)")
    print(f"  convex pairs kept:            {st['pairs_convex']}")
    print(f"edge groups (merged runs):      {st['groups_candidate']}")
    print(f"  rejected short (< min-len):   {st['rej_short']}")
    print(f"  rejected thin (r < min-radius):{st['rej_thin_face']}")
    print(f"  rejected concave (group):     {st['rej_concave_group']}")
    print(f"  bevelled groups:              {st['groups_bevelled']}  total length {st['bevelled_length']:.0f} units")
    if st["align_shifted"] or st["align_drift"] or st["align_scale"]:
        print(f"align: shifted {st['align_shifted']} components ({st['align_faces']} faces, mean |shift| "
              f"{st['align_shift_sum'] / max(1, st['align_shifted']):.3f} period); skipped: other shader {st['align_other_shader']}, "
              f"scale {st['align_scale']}, drifting mapping {st['align_drift']}")
    print(f"uv pairs: morph {st['uv_morph_pairs']}, seam (different shader) {st['uv_seam_pairs_other_shader']}, "
          f"seam (scale ratio > 1.5 fallback) {st['uv_seam_pairs_scale_fallback']}"
          + (f"; mean leftover st offset {st['uv_residual_sum'] / st['uv_morph_pairs']:.3f}" if st['uv_morph_pairs'] else ""))
    print(f"face tris {st['face_tris']} from {st['face_poly_verts']} polygon verts")
    print(f"face polygons: {st['face_polys_before_merge']} pieces -> {st['face_polys_after_merge']} after merging")
    print(f"strip rows: {st['strip_rows_candidate']} candidates, {st['strip_rows_kept']} kept")
    print(f"adaptive radius (smaller than --radius): {st['groups_adaptive_radius']} of {st['groups_bevelled']} runs")
    print(f"box corners: found {st['corners_found']}, patched {st['corner_patches']} ({st['corner_patch_tris']} tris), reverted to taper {st['corners_reverted']}; "
          f"rejected: not 3 runs {st['corner_rej_not_three_runs']}, not a box vertex {st['corner_rej_not_a_box_vertex']}, not orthogonal {st['corner_rej_not_orthogonal']}, skewed {st['corner_rej_skewed']}")
    print(f"wall ends: {st['wall_ends']} (end-row mismatch >0.3u {st['wall_end_row_mismatch']}; under-wall, no cap needed {st['wall_ends_under']}; caps {st['wall_caps']}, {st['wall_cap_tris']} tris), rejected: no wall plane {st['wall_rej_no_plane']}, "
          f"no hole boundary {st['wall_rej_no_hole']}")
    print(f"run ends of bevelled runs: {dict(collections.Counter(k for k, _p in bv.end_log))}; wall flags reverted to taper (overlap/coverage) {st['wall_ends_reverted_overlap']}")
    print(f"mitres: {st['mitres_found']} of {st['mitre_cand']} candidate bends (rejected: planes {st['mitre_rej_planes']}, radius/angle {st['mitre_rej_radius_angle']}, "
          f"not a reflex L {st['mitre_rej_not_reflex_L']}); reverted: overlap {st['mitres_reverted_overlap']}, partner {st['mitres_reverted_partner']}; "
          f"failed with mitre: coverage {st['mitre_fail_rej_face_coverage']}, overlap {st['mitre_fail_rej_overlap_run']}; asymmetric {st['mitre_asymmetric']}, corner vertex missing {st['mitre_corner_vertex_missing']}")
    print(f"strip triangles added:          {st['strip_tris']}  (degenerate skipped {st['strip_tris_degenerate_skipped']}, "
          f"centre mismatches {st['strip_center_mismatch']})")
    print(f"  rejected cut region off face: {st['rej_face_coverage']}")
    print(f"  rejected overlapping runs:    {st['rej_overlap_run']}")
    print(f"  faces reverted (>1024 verts): {st['faces_reverted_over_vert_limit']}, fully cut away (kept stock) {st['faces_emptied_kept_stock']}")
    print(f"surfaces modified:              {st['surfaces_modified']} (kept planar {st['surfaces_kept_planar']}, "
          f"converted to trisoup {st['surfaces_converted_to_trisoup']})")
    print(f"drawverts:   {st['verts_before']} -> {st['verts_after']} (compacted: stock ranges of rewritten surfaces dropped, {st["verts_orphaned"]} verts)")
    print(f"drawindexes: {st['indexes_before']} -> {st['indexes_after']}")


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", default="escape1")
    ap.add_argument("--pk3", nargs="?", const=str(DEFAULT_PK3), metavar="OUT.pk3", help=f"write the pack (default {DEFAULT_PK3})")
    ap.add_argument("--radius", type=float, default=3.0, help="setback of the cut from the edge on each face, in units")
    ap.add_argument("--segments", type=int, default=3, help="arc segments (a vertex is always put at the arc middle, the texture seam)")
    ap.add_argument("--taper", type=float, default=None, help="length over which the cut ramps 0->radius at each interval end (default 2*radius)")
    ap.add_argument("--min-angle", type=float, default=60.0, help="min angle between the two face normals (deg)")
    ap.add_argument("--max-angle", type=float, default=135.0)
    ap.add_argument("--row-tol", type=float, default=0.0, help="drop strip rows whose cut vertices lie within this distance of the line through the neighbouring rows (0 = keep all)")
    ap.add_argument("--min-length", type=float, default=4.0, help="min shared edge interval length")
    ap.add_argument("--min-radius", type=float, default=1.0, help="skip a run whose adaptive radius (min(radius, 0.45 x smaller face extent)) is below this")
    ap.add_argument("--skip-shader", default=DEFAULT_SKIP, help="regex of shader names to leave alone ('' disables)")
    ap.add_argument("--surface-type", choices=("face", "tri"), default="face",
                    help="face = keep type 1 (needs the engine's BSP_MAX_FACE_VERTS patch; a face over 1024 verts is left unbevelled); "
                         "tri = convert modified surfaces to type 3 (rend2 then ignores the lightmap page)")
    ap.add_argument("--uv-mode", choices=("seam", "morph", "align"), default="seam",
                    help="morph: blend st from face A's mapping to face B's (shifted by an integer) across the strip when both "
                         "faces use the same shader and similar texture scale; seam: each half keeps its own face's mapping")
    ap.add_argument("--no-merge-polys", dest="merge_polys", action="store_false", help="keep the clipped face pieces unmerged (more triangles)")
    ap.add_argument("--dump-rej", nargs=6, type=float, metavar=("X0", "Y0", "Z0", "X1", "Y1", "Z1"),
                    help="debug: print the run-end vertices (kind, position) logged inside this box")
    ap.add_argument("--wall-ends", action=argparse.BooleanOptionalAction, default=True,
                    help="run ends that butt into a wall keep the full radius up to the wall and get a cap (default on)")
    ap.add_argument("--mitre", action=argparse.BooleanOptionalAction, default=True,
                    help="two runs of one plane bending around a reflex (L-shaped) outline are mitred instead of tapered (default on)")
    ap.add_argument("--wall-dot", type=float, default=0.99, help="min cos between the run direction and the wall normal for a wall end")
    ap.add_argument("--smooth-models", nargs="?", const=DEFAULT_SMOOTH, default=None, metavar="REGEX",
                    help="also Loop-smooth baked misc_model trisoup surfaces whose shader matches REGEX (default regex if omitted)")
    ap.add_argument("--no-bevel", action="store_true", help="skip the corner bevel (use with --smooth-models)")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--roundtrip", action="store_true")
    ap.add_argument("--all", action="store_true", help="with --roundtrip: every map in run/main/*.pk3")
    ap.add_argument("--obj", metavar="OUT.obj", help="dump world triangles in --region before/after (OUT_before.obj / OUT_after.obj)")
    ap.add_argument("--region", nargs=6, type=float, metavar=("X0", "Y0", "Z0", "X1", "Y1", "Z1"))
    return ap


def main():
    a = build_parser().parse_args()
    if a.roundtrip:
        sys.exit(0 if cmd_roundtrip(a.all) else 1)
    data = find_bsp(a.map)
    orig = Bsp(data)
    bv = Bevel(orig, a)
    new = orig if a.no_bevel else bv.run()
    if a.smooth_models is not None:
        new = smooth_trisoup(new, a.smooth_models)
        new = smooth_brush_props(new)
    print_stats(bv) if (not a.no_bevel) and (a.stats or not (a.pk3 or a.obj or a.validate)) else None
    if a.dump_rej:
        lo, hi = np.array(a.dump_rej[:3]), np.array(a.dump_rej[3:])
        sel = [(k, p) for k, p in bv.rej_log + bv.end_log if (p >= lo).all() and (p <= hi).all()]
        print("run ends in box:", dict(collections.Counter(k for k, _p in sel)))
        for k, p in sorted(sel, key=lambda x: (x[0], tuple(x[1]))):
            print(f"   {k:7s} {np.round(p, 1)}")
    if a.validate:
        res, gaps = validate(orig, new, bv)
        for name, ok, det in res:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}  {det}")
        for pa, pb in gaps[:(100000 if os.environ.get("WB_GAPS") else 10)]:
            print("   unmatched strip edge", np.round(pa, 3), np.round(pb, 3))
    if a.obj:
        base = a.obj[:-4] if a.obj.endswith(".obj") else a.obj
        write_obj(base + "_before.obj", orig, a.region)
        write_obj(base + "_after.obj", new, a.region)
    if a.pk3:
        write_pk3(a.pk3, a.map, new.write())


if __name__ == "__main__":
    main()
