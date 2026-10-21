#!/usr/bin/env python3
"""Bake rend2 specular maps (`<texture>_s.png`) for hand-tagged RTCW materials.

Reads the owned game paks (and the local HD pack, if present), writes a private pk3 that rend2
auto-loads (r_specularMapping 1): rgb = reflectance at normal incidence, alpha = gloss.
Output is a derivative of proprietary textures: never commit or redistribute it.

  python3 -I tools/spec-bake/spec_bake.py [--out run/codmod/codmod_spec.pk3] [--list]
"""
import argparse, io, re, sys, zipfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
PAKS = [ROOT / "run/main" / n for n in ("pak0.pk3", "sp_pak1.pk3", "sp_pak2.pk3", "sp_pak3.pk3", "sp_pak4.pk3")]
HD = ROOT / "run/codmod/codmod_hd.pk3"
ZFIX = ROOT / "run/codmod/codmod_zfix.pk3"  # tools/asset-fixes output: highest priority

# material: (F0 base, F0 luma gain, tint toward diffuse colour, gloss base, gloss luma gain)
MATERIALS = {
    "gunmetal": (0.30, 0.45, 0.35, 0.55, 0.35),
    "metal":    (0.22, 0.38, 0.40, 0.40, 0.35),
    "armor":    (0.35, 0.45, 0.60, 0.55, 0.30),
    "wood":     (0.03, 0.02, 0.00, 0.17, 0.20),
    "marble":   (0.05, 0.03, 0.00, 0.55, 0.30),
    "stone":    (0.04, 0.02, 0.00, 0.28, 0.25),
    "glass":    (0.05, 0.00, 0.00, 0.85, 0.10),
    "ceramic":  (0.05, 0.02, 0.00, 0.65, 0.20),
}
# Ordered regex rules on the lowercase path without extension; first match wins. "skip" = no map.
RULES = [
    # never: effects, unlit/emissive/sprite art, skin and cloth-only parts, water, helper files
    ("skip", r"(^gfx/|levelshots|/ammo/|bread|sausage|pillow|bedlinen|heinrich(bod|ead)|clipboard/wood|shard|shadow|flare|icon|flash|flame|fire|ember|cloud|fog|skies|/sfx/|decals|effects|fonts|/sign|picture|/flag|"
             r"letter|anatomy|hay|blood|torch|liquids|/lights/|glow|test|\.blend|_alpha|/maps/|/the_end/|/intro/|/chat/|"
             r"_head|/hand|arm\d|legs|foot|shell|zap|_body|_boot|cap$|/cig|/terrain/|/tree/|/plants/|/rubble/)"),
    ("gunmetal", r"^models/weapons2/|^models/mapobjects/weapons/"),
    ("armor", r"^models/powerups/armor/|vacum/armor|knight/(knt|weap)(?!_stone)|players/.*(helm|_bp|armor|mask|bar1)"),
    ("glass", r"glass|freeze_glass|c_glass|/tube$"),
    ("ceramic", r"archeology/(jug|vase)"),
    ("metal", r"metal|steel|iron|machine_|atool|atruss|elec1|mesure|assault/panel|xpanel|panel_|controlpanel|/train|"
              r"track_|tram|sawblade|rocket|flywheel|stove|file_cab|lockers|barrel|kobra|/sub\d|cable|xgrid|xradio|"
              r"tank_top|nxlab/|mdoor|cagelight|cage_light|chandl|pendant|sconce|bel_lamp|base_lamp|furnace|generator|"
              r"chain|xsink|shovel|/tools|weldtanks|mapobjects/vehicles/|electronics/|gold_m|silverware|candle|trim_c0[356]b?$"),
    ("marble", r"marble"),
    ("stone", r"chateau/(floor|stair)|castle_floor|town_floor|xlab_floor"),
    ("wood", r"wood|desk|chair|table|board_|box_m|castle_door|town_door|textures/doors/|chateau/door|"
             r"shudder|crate|book_c|loveseat|wag_|furniture"),
]
MAX_SIDE = 1024  # specular detail does not need the HD size


# Chains are vertex-lit (rgbGen vertex/identity), which bypasses rend2's lit shader path, so no specular could ever
# reach them. Override their shaders to rgbGen lightingDiffuse (autoSprite2 chain2 stays unlit: deforms are not lit).
SHADER = """// codmod specular: lit chains
models/mapobjects/chain/chain
{
	cull disable
	{
		map models/mapobjects/chain/chain.tga
		alphaFunc GE128
		depthWrite
		rgbGen lightingDiffuse
	}
}
models/mapobjects/chain/chain3
{
	cull disable
	{
		map models/mapobjects/chain/chain3.tga
		alphaFunc GE128
		depthWrite
		rgbGen lightingDiffuse
	}
}
models/mapobjects/corpse/chain
{
	cull disable
	{
		map models/mapobjects/corpse/chain.tga
		alphaFunc GE128
		depthWrite
		rgbGen lightingDiffuse
	}
}
"""


def material_for(stem):
    st = stem.lower()
    if st.endswith(("_s", "_n", "_nh", "_h")):
        return None
    for mat, pat in RULES:
        if re.search(pat, st):
            return None if mat == "skip" else mat
    return None


def collect():
    """stem -> (zip path, member); zfix wins over HD, HD over originals, later paks over earlier."""
    found = {}
    for pk in [p for p in PAKS if p.exists()] + [p for p in (HD, ZFIX) if p.exists()]:
        with zipfile.ZipFile(pk) as z:
            for n in z.namelist():
                stem, dot, ext = n.rpartition(".")
                if dot and ext.lower() in ("tga", "jpg", "png") and material_for(stem):
                    found[stem] = (pk, n)
    return found


def bake(img, mat):
    f0b, f0g, tint, glb, glg = MATERIALS[mat]
    if max(img.size) > MAX_SIDE:
        img = img.resize((max(1, img.width * MAX_SIDE // max(img.size)), max(1, img.height * MAX_SIDE // max(img.size))), Image.LANCZOS)
    rgb = np.asarray(img.convert("RGB"), np.float32) / 255.0
    luma = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    lo, hi = np.percentile(luma, (5, 95))
    l = np.clip((luma - lo) / max(hi - lo, 1e-3), 0, 1)
    # keep crevices dull: low detail luminance kills the highlight
    blur = np.asarray(Image.fromarray((luma * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32) / 255
    cav = np.clip(0.75 + (luma - blur) * 4.0, 0.3, 1.0)
    # near-black texels (noise, unused atlas space): no tint, and F0/gloss fade to ~0 (absolute luma)
    ss = lambda a, b, x: (lambda t: t * t * (3 - 2 * t))(np.clip((x - a) / (b - a), 0, 1))
    dark = ss(0.006, 0.035, luma)
    f0 = (f0b + f0g * l) * cav * dark
    colour = rgb / np.maximum(luma[..., None], 1e-3)
    colour = 1 + (np.clip(colour, 0.4, 2.0) - 1) * ss(0.02, 0.12, luma)[..., None]
    f0rgb = f0[..., None] * ((1 - tint) + tint * colour)
    gloss = np.clip((glb + glg * l) * cav * dark, 0, 1)
    out = np.dstack([np.clip(f0rgb, 0, 1), gloss])
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "run/codmod/codmod_spec.pk3"))
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    found = collect()
    if a.list:
        for s in sorted(found):
            print(f"{material_for(s):9s} {s}")
        return
    n = 0
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as zo:
        zo.writestr("scripts/codmod_spec.shader", SHADER)
        for stem, (pk, member) in sorted(found.items()):
            with zipfile.ZipFile(pk) as z:
                img = Image.open(io.BytesIO(z.read(member)))
                img.load()
            buf = io.BytesIO()
            bake(img, material_for(stem)).save(buf, "PNG")
            zo.writestr(f"{stem}_s.png", buf.getvalue())
            n += 1
    print(f"wrote {n} specular maps to {a.out}")


if __name__ == "__main__":
    sys.exit(main())
