#!/usr/bin/env python3
"""Private per-texture asset fixes for broken RTCW art -> run/codmod/codmod_zfix.pk3.

Reads each source texture from the owned game paks (HD pack preferred when it has the file), applies a fix from
FIXES and writes the result (same path, same size, RGBA TGA) into a pk3 that sorts after codmod_hd.pk3 so it
overrides it. Output is a derivative of proprietary textures: never commit or redistribute it.

  python3 -I tools/asset-fixes/fix_assets.py [--out run/codmod/codmod_zfix.pk3] [--list] [--preview DIR]

--preview DIR writes <name>_before_after.png (UV wireframe of the model overlaid) and prints a crude check.
Order: hd-textures -> fix_assets -> spec-bake (spec-bake must read codmod_zfix.pk3 before codmod_hd.pk3).
"""
import argparse, io, struct, sys, zipfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
PAKS = [ROOT / "run/main" / n for n in ("pak0.pk3", "sp_pak1.pk3", "sp_pak2.pk3", "sp_pak3.pk3", "sp_pak4.pk3")]
HD = ROOT / "run/codmod/codmod_hd.pk3"


def read_file(path):
    """Newest pak wins (HD pack first). Returns (bytes, source label) or (None, None)."""
    for pk in [HD] + PAKS[::-1]:
        if not pk.exists():
            continue
        with zipfile.ZipFile(pk) as z:
            names = {n.lower(): n for n in z.namelist()}
            if path.lower() in names:
                return z.read(names[path.lower()]), pk.name
    return None, None


def feather_mask(poly, size, grow, blur):
    """Filled UV polygon (uv coords), grown by `grow` px and softened by `blur` px, as float 0..1."""
    w, h = size
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon([(u * w, v * h) for u, v in poly], fill=255)
    if grow:
        m = m.filter(ImageFilter.MaxFilter(grow * 2 + 1))
    return np.asarray(m.filter(ImageFilter.GaussianBlur(blur)), dtype=np.float32) / 255.0


def armor_stats(img, poly):
    """(median luma, median alpha) of the non-black texels outside `poly` (the actual armor)."""
    a = np.asarray(img.convert("RGBA")).astype(np.float32)
    keep = (feather_mask(poly, img.size, 4, 0) < 0.5) & (a[..., :3].mean(2) > 8)
    return float(np.median(a[..., :3].mean(2)[keep])), float(np.median(a[..., 3][keep]))


def paste_patch(img, donor_box, poly, grow=3, blur=2.0, luma=None, alpha=None):
    """Fill the UV polygon with the donor box (uv x0,y0,x1,y1) scaled to the polygon's bounding box."""
    w, h = img.size
    a = np.asarray(img.convert("RGBA"), dtype=np.float32)
    x0, y0, x1, y1 = donor_box
    donor = img.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)))
    us = [p[0] for p in poly]; vs = [p[1] for p in poly]
    bx0, by0, bx1, by1 = (round(min(us) * w) - grow * 2, round(min(vs) * h) - grow * 2,
                          round(max(us) * w) + grow * 2, round(max(vs) * h) + grow * 2)
    donor = donor.resize((bx1 - bx0, by1 - by0), Image.LANCZOS)
    layer = np.zeros_like(a)
    layer[by0:by1, bx0:bx1] = np.asarray(donor.convert("RGBA"), dtype=np.float32)
    if luma is not None:  # rescale so the patch's mean luma is `luma` (keeps the plate's shading)
        layer[..., :3] = np.clip(layer[..., :3] * luma / max(layer[by0:by1, bx0:bx1, :3].mean(), 1), 0, 255)
    if alpha is not None:
        layer[..., 3] = alpha
    m = feather_mask(poly, img.size, max(1, round(grow * w / 256)), blur * w / 256)[..., None]
    out = a * (1 - m) + layer * m
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), "RGBA")


# Knight statue (models/mapobjects/knight/knight_anim.mdc): the pauldron/plate triangles of surfaces torso04,
# l_hand_new, head, rt_foot, rt_elbow_new (x2), leg_l04 and rtthigh map into an empty (pure black, alpha 255) diamond
# between the wooden panel and the helmet. It is a dump spot for hidden/cap faces (helmet interior, neck hole, limb
# caps), so fill it with the smooth helmet-side plate darkened to dull steel (0.5x the armor's median luma) and the
# armor's typical alpha, so the env reflection reads as metal but subdued.
KNT_DIAMOND = [(0.75, 0.035), (0.865, 0.14), (0.755, 0.255), (0.645, 0.14)]
KNT_DONOR = (0.07, 0.02, 0.29, 0.24)


def fix_knt(img):
    med_luma, med_alpha = armor_stats(img, KNT_DIAMOND)
    return paste_patch(img, KNT_DONOR, KNT_DIAMOND, grow=3, blur=2.0, luma=0.5 * med_luma, alpha=med_alpha)


# path -> (fix function, checked region polygon in uv, mdc used for previews)
FIXES = {
    "models/mapobjects/knight/knt.tga": (fix_knt, KNT_DIAMOND, "models/mapobjects/knight/knight_anim.mdc"),
}


def region_stats(img, poly):
    w, h = img.size
    m = np.asarray(feather_mask(poly, img.size, 0, 0)) > 0.5
    px = np.asarray(img.convert("RGBA"))[m].astype(float)
    return px[:, :3].mean(), px[:, 3].mean(), (px[:, :3].mean(1) < 6).mean()


def mdc_tris(data):
    """Yield (surface name, [(u,v)*3]) for every triangle of an MDC (surface header is '<4s64s14i')."""
    h = struct.unpack_from("<4si64si4i5i", data, 0)
    ofs = h[11]
    for _ in range(h[6]):
        sh = struct.unpack_from("<4s64s14i", data, ofs)
        name = sh[1].split(b"\0")[0].decode()
        st = [struct.unpack_from("<2f", data, ofs + sh[10] + i * 8) for i in range(sh[6])]
        for i in range(sh[7]):
            yield name, [st[j] for j in struct.unpack_from("<3i", data, ofs + sh[8] + i * 12)]
        ofs += sh[-1]


def preview(path, before, after, mdc, outdir):
    S = 1024
    tiles = []
    for im in (before, after):
        t = im.convert("RGB").resize((S, S), Image.LANCZOS)
        t = Image.eval(t, lambda v: min(255, v * 3))  # brighten: the atlas is very dark
        d = ImageDraw.Draw(t)
        for _, uv in mdc_tris(mdc):
            d.polygon([((u % 1) * S, (v % 1) * S) for u, v in uv], outline=(255, 60, 60))
        tiles.append(t)
    sheet = Image.new("RGB", (S * 2 + 8, S), (255, 255, 255))
    sheet.paste(tiles[0], (0, 0)); sheet.paste(tiles[1], (S + 8, 0))
    out = Path(outdir) / (Path(path).stem + "_before_after.png")
    sheet.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "run/codmod/codmod_zfix.pk3"))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--preview", metavar="DIR")
    a = ap.parse_args()
    if a.list:
        for p in FIXES:
            print(p)
        return 0
    results = {}
    for path, (fn, poly, mdc_path) in FIXES.items():
        raw, src = read_file(path)
        if raw is None:
            print(f"skip {path}: not found in any pak"); continue
        before = Image.open(io.BytesIO(raw)); before.load()
        before = before.convert("RGBA")
        after = fn(before)
        assert after.size == before.size and after.mode == "RGBA"
        b, af = region_stats(before, poly), region_stats(after, poly)
        print(f"{path} [{src}, {before.size[0]}x{before.size[1]}] region mean rgb {b[0]:.1f}->{af[0]:.1f}, "
              f"alpha {b[1]:.0f}->{af[1]:.0f}, near-black fraction {b[2]:.2f}->{af[2]:.2f}")
        if af[2] > 0.5 or af[0] < 8:  # dull steel is intentionally dark
            print("  WARNING: patched region still looks near-black")
        buf = io.BytesIO(); after.save(buf, "TGA", rle=False)
        results[path] = buf.getvalue()
        if a.preview:
            Path(a.preview).mkdir(parents=True, exist_ok=True)
            mdc, _ = read_file(mdc_path)
            print("  preview:", preview(path, before, after, mdc, a.preview))
    if not results:
        return 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for p, d in results.items():
            z.writestr(p, d)
    print(f"wrote {a.out} ({len(results)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
