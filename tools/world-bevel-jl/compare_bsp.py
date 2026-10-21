"""Compare the BSP inside two pk3s (Python vs Julia bevel output).  python3 -I compare_bsp.py A.pk3 B.pk3 MAP"""
import struct, sys, zipfile
import numpy as np

def load(pk3, name):
    z = zipfile.ZipFile(pk3)
    d = z.read(f"maps/{name}.bsp")
    lumps = [struct.unpack_from("<ii", d, 8 + 8 * i) for i in range(17)]
    return d, lumps, {n: z.read(n) for n in z.namelist() if n.endswith(".aas")}

def main():
    pa, pb, name = sys.argv[1:4]
    A, B = load(pa, name), load(pb, name)
    la, lb = A[1], B[1]
    ok = True
    for i in range(17):
        if i in (10, 11, 13):
            continue
        same = A[0][la[i][0]:la[i][0] + la[i][1]] == B[0][lb[i][0]:lb[i][0] + lb[i][1]]
        if not same:
            ok = False
            print(f"lump {i} differs")
    print("other lumps identical" if ok else "OTHER LUMPS DIFFER")
    def arr(X, i, dt):
        d, l = X[0], X[1]
        return np.frombuffer(d, dtype=dt, count=l[i][1] // dt.itemsize, offset=l[i][0])
    dv = np.dtype([("xyz", "<f4", 3), ("st", "<f4", 2), ("lm", "<f4", 2), ("n", "<f4", 3), ("c", "u1", 4)])
    sf = np.dtype([("shader", "<i4"), ("fog", "<i4"), ("typ", "<i4"), ("fv", "<i4"), ("nv", "<i4"), ("fi", "<i4"), ("ni", "<i4"), ("rest", "u1", 104 - 28)])
    VA, VB = arr(A, 10, dv), arr(B, 10, dv)
    IA, IB = arr(A, 11, np.dtype("<i4")), arr(B, 11, np.dtype("<i4"))
    SA, SB = arr(A, 13, sf), arr(B, 13, sf)
    print("surfaces", len(SA), len(SB), "| drawverts", len(VA), len(VB), "| drawindexes", len(IA), len(IB))
    for nm, V in (("A", VA), ("B", VB)):
        print(nm, "NaN:", bool(np.isnan(V["xyz"]).any() or np.isnan(V["st"]).any() or np.isnan(V["n"]).any()))
    for nm, S, V, I in (("A", SA, VA, IA), ("B", SB, VB, IB)):
        bad = 0
        for s in S:
            if s["ni"] and (I[s["fi"]:s["fi"] + s["ni"]].max() >= s["nv"] or s["fv"] + s["nv"] > len(V)):
                bad += 1
        print(nm, "surfaces with out-of-range indexes:", bad)
    print("shader/fog/typ identical:", all((SA[k] == SB[k]).all() if False else True for k in ()) , 
          bool((SA["shader"] == SB["shader"]).all()), bool((SA["fog"] == SB["fog"]).all()), bool((SA["typ"] == SB["typ"]).all()))
    dn = np.nonzero((SA["nv"] != SB["nv"]) | (SA["ni"] != SB["ni"]))[0]
    print("surfaces with different nv/ni:", len(dn), dn[:15].tolist())
    for k in dn[:8]:
        print("   surf", k, "A nv/ni", SA[k]["nv"], SA[k]["ni"], "B", SB[k]["nv"], SB[k]["ni"], "typ", SA[k]["typ"])
    def stats(S, V, I):
        tot, lo, hi = 0.0, np.full(3, 1e30), np.full(3, -1e30)
        per = np.zeros(len(S))
        for k, s in enumerate(S):
            if not s["ni"]:
                continue
            v = V[s["fv"]:s["fv"] + s["nv"]]["xyz"].astype(np.float64)
            t = I[s["fi"]:s["fi"] + s["ni"]].reshape(-1, 3)
            c = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
            per[k] = 0.5 * np.linalg.norm(c, axis=1).sum()
            lo, hi = np.minimum(lo, v.min(0)), np.maximum(hi, v.max(0))
        return per.sum(), lo, hi, per
    ta, lo_a, hi_a, pa_ = stats(SA, VA, IA)
    tb, lo_b, hi_b, pb_ = stats(SB, VB, IB)
    print(f"total triangle area A {ta:.3f} B {tb:.3f} rel diff {(tb - ta) / ta:.2e}")
    print("bbox A", lo_a, hi_a, "\nbbox B", lo_b, hi_b)
    d = np.abs(pa_ - pb_)
    w = np.argsort(-d)[:8]
    print("largest per-surface area diffs:", [(int(k), round(float(pa_[k]), 2), round(float(pb_[k]), 2)) for k in w])
    print("surfaces with area diff > 1e-3 rel:", int((d > 1e-3 * np.maximum(pa_, 1e-9)).sum()))
    for n in sorted(set(A[2]) | set(B[2])):
        a, b = A[2].get(n), B[2].get(n)
        print(n, "AAS identical except checksum" if a and b and a[:8] == b[:8] and a[12:] == b[12:] else "AAS differs", 
              hex(struct.unpack_from("<I", a, 8)[0]) if a else None, hex(struct.unpack_from("<I", b, 8)[0]) if b else None)
main()
