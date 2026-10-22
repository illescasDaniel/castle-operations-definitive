#!/usr/bin/env python3
"""Seam metrics for the bevel lighting work (v2).

usage: scripts/seam-metric.py [--regions FILE] DIR_OR_FILES...   (tga/png; a directory means its spot*.tga/png)

Per shot (the top 70 rows with console text are ignored; luminance 0-255):
  jump    old metric: largest jump of the column-mean luminance between adjacent columns over the whole image (and its x).
  ratio   strip / neighbours: mean luminance in the strip x-range over the mean of the 40 px to its left and right.
  d2      largest |second difference| of the column means within the strip range +-10 px (a thin Mach line or a step).
  mirror  mirror score: correlation of the high-passed luminance left of the strip centre with the mirror image right of it
          (best axis inside the strip range; a visibly mirrored corner scores ~0.2 here, an unrelated one ~0.0). Only meaningful for same-shader corners.
The strip x-ranges come from benchmarks/spots-tram.regions (spot index, x0, x1)."""
import sys, glob, os
from PIL import Image
import numpy as np

SKIP_TOP = 70

def load_regions(path):
    reg = {}
    if path and os.path.exists(path):
        for l in open(path):
            l = l.split("#")[0].split()
            if len(l) == 3:
                reg[int(l[0])] = (int(l[1]), int(l[2]))
    return reg

def blur(a, k=15):
    ker = np.ones(k) / k
    return np.apply_along_axis(lambda r: np.convolve(r, ker, mode="same"), 1, a)

def metric(path, region):
    im = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)[SKIP_TOP:]
    y = 0.299 * im[..., 0] + 0.587 * im[..., 1] + 0.114 * im[..., 2]
    col = y.mean(axis=0)
    d = np.abs(np.diff(col)); d[:20] = 0; d[-20:] = 0
    i = int(d.argmax())
    out = {"jump": float(d[i]), "x": i}
    if region:
        x0, x1 = region
        neigh = np.concatenate([col[max(0, x0 - 40):x0], col[x1:x1 + 40]])
        out["ratio"] = float(col[x0:x1].mean() / max(neigh.mean(), 1e-6))
        lo, hi = max(1, x0 - 10), min(len(col) - 1, x1 + 10)
        dd = np.abs(col[lo + 1:hi + 1] - 2 * col[lo:hi] + col[lo - 1:hi - 1])
        out["d2"] = float(dd.max())
        hp = y - blur(y, 9)
        best = 0.0
        for c in range(x0, x1 + 1):
            K = min(80, c - 5, y.shape[1] - c - 6)
            L = hp[:, c - K:c][:, ::-1]
            R = hp[:, c:c + K]
            num = (L * R).sum(axis=1); den = np.sqrt((L * L).sum(axis=1) * (R * R).sum(axis=1)) + 1e-9
            ok = den > 1e-3 * K
            if ok.any():
                best = max(best, float(np.mean(num[ok] / den[ok])))
        out["mirror"] = best
    return out

def main(args):
    reg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "benchmarks", "spots-tram.regions")
    if args and args[0] == "--regions":
        reg_path = args[1]; args = args[2:]
    regions = load_regions(reg_path)
    files = []
    for a in args:
        if os.path.isdir(a):
            files += sorted(glob.glob(os.path.join(a, "spot*.tga")) + glob.glob(os.path.join(a, "spot*.png")))
        else:
            files.append(a)
    for f in files:
        b = os.path.basename(f)
        try:
            idx = int(b[4:6])
        except ValueError:
            idx = 0
        m = metric(f, regions.get(idx))
        s = f"{os.path.basename(os.path.dirname(f))}/{b}: jump {m['jump']:6.2f} at x={m['x']:4d}"
        if "ratio" in m:
            s += f"  ratio {m['ratio']:.2f}  d2 {m['d2']:5.2f}  mirror {m['mirror']:.2f}"
        print(s)

if __name__ == "__main__":
    main(sys.argv[1:] or ["."])
