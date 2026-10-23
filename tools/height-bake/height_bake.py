#!/usr/bin/env python3
"""Bake rend2 normal+height maps (`<texture>_nh.png`: rgb = tangent-space normal, alpha = height) for wall/floor
textures with DeepBump (AI colour->normal, https://github.com/HugoTini/DeepBump, GPLv3, ONNX).
Output is a derivative of proprietary textures: never commit or redistribute it.

  tools/height-bake/.venv/bin/python -I tools/height-bake/height_bake.py --map escape1 [--list] [--preview]

Pipeline per texture: albedo (zfix > hd > paks, max 1024) -> DeepBump normals (wrap-padded, overlapping tiles)
-> FFT Frankot-Chellappa integration (periodic) -> high-pass + a little albedo-luma detail -> PLATEAU normalisation
(tops of bricks/cobbles = 1.0 = the geometric plane, so props do not float) -> normals recomputed from final height.
"""
import argparse, hashlib, io, json, os, re, struct, sys, time, zipfile
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAKS = [ROOT / "run/main" / n for n in ("pak0.pk3", "sp_pak1.pk3", "sp_pak2.pk3", "sp_pak3.pk3", "sp_pak4.pk3")]
HD = ROOT / "run/codmod/codmod_hd.pk3"
ZFIX = ROOT / "run/codmod/codmod_zfix.pk3"
CACHE = HERE / "cache"
VERSION = 2   # bump when the maths changes in a way the cache key does not see
THREADS = 0   # onnxruntime intra-op threads per process (0 = library default)
# textures that gate as good but look wrong in the full-game review (pillowy tile floors, striped trim): forced flat
DEFAULT_FLATTEN = r"xfloor_c03b|bricktrim_c06"
MODEL = HERE / "models/deepbump256.onnx"
MODEL_URL = "https://github.com/HugoTini/DeepBump/raw/master/deepbump256.onnx"
MAX_SIDE = 1024
TILE = 256

# Ordered regex rules on the lowercase texture stem; first match wins. "skip" = no map.
RULES = [
    ("skip", r"(decals|/sfx/|sky|skies|glass|window(?!/shudder)|/alpha/|/lights/|light_|fog|flame|ember|torch|/tree/|"
             r"/common/|/sign|flag|picture|haze|/models/|^models)"),
    # props (crates, barrels, train parts) are shared with free-standing brushes: normals only, never parallax
    ("prop", r"/props/|castle_props|/barrel|/box_|/crate"),
    ("floor", r"floor"),
    ("wood", r"castle_wood|town_wood|textures/wood/|s_cwood|castle_door|shudder|door_c|chwood|chat_wood|mdoor|plank|board"),
    ("rock", r"textures/rock/|terrain|mountain"),
    ("concrete", r"concrete"),
    # metal wants clean specular, not relief: normals only (see docs/normals-coverage-plan.md)
    # painted/riveted sheet steel (xlab panels): smooth in reality, DeepBump invents pitting, so a weak normal strength
    ("panel", r"xmetal|x_metalwall"),
    ("metal", r"metal|atool|/xlab_m|pipe|rivet|steel|iron|grate|vent"),
    # marble is stone-like but polished: normals only for now
    ("marble", r"marble"),
    # burnt floors: an ember underlay shows through, rend2 lights only the blended top stage; normals only, no parallax
    ("burnt", r"burn_flr"),
    ("brick", r"castle_wall|cathedrale_wall|/s_castle|/s_cathedrale|/s_roof|chateau|town_wall|brick|cobble|mortar|plaster|stone|"
              r"wall|crypt|debri|rubble|gy_|vill_c|dirt|trim|step|stair|pillar|column|arch|roof|tile"),
    # everything else that is an opaque lit diffuse: normals only (safe default)
    ("other", r".*"),
]
# classes baked normals-only (alpha height flat, so parallax never runs on them)
NORMALS_ONLY = {"model", "prop", "metal", "panel", "marble", "burnt", "other"}
# multiplier on the normal relief (pixels) for smooth-surface classes
CLASS_STRENGTH = {"panel": 0.25, "marble": 0.5}
# `--preset NAME` = the model packs as shipped: (--models regex, --exclude regex, --models-opaque, default --out)
PRESETS = {
    "props": (r"^models/(mapobjects|powerups|ammo|flags|furniture)/",
              r"/(tree|snow_tree|plants|bush|sky|shards|shard)/|glass|/(light|lamps|lamp|flares|lightning|gratelamp|colua0|xlab_props)/|"
              r"flare|shadow|beam|water|goo|bpblood|gibs|radarbeeps|radarsweep|/fire|propeller|parachute|hologirl|portal|scoreboard|"
              r"arenalogo|_ui_|bjui/|letters/|c_bibbles|/cin$|skull_spirit|/test/|/test2?/|characters/test|temphead|templower|"
              r"tempupper|ghost|elec[0-9]|cagelight|cage_light|camplt|sconce|chandlier|bel_lamp|pendant|light_m4|desklamp|dirt|blink|end/castle",
              True, "run/codmod/codmod_height_models.pk3"),
    "players": (r"^models/players/",
                r"blink|glass|glow|zom_hair|hein_hair|helgrass|ghost|elec[0-9]|/eyes?|_eye|flash|/hand16$|/arm2$|/bj_legs$|/g_bitterman|"
                r"anarki_board|/doom/|brandon/|_stim|dh_mon|beast/mouth|beast/skulls2|/spark$|/fire$|/goo1$|escape_env",
                True, "run/codmod/codmod_height_players.pk3"),
    "weapons": (r"weapons2/(?!.*(flash|flame|zap_scroll|hand16|arm2|bj_legs|m_shell))", None, False,
                "run/codmod/codmod_height_weapons.pk3"),
}
# shader scripts with these surfaceparms / keywords are never baked (not an opaque lit diffuse surface)
BAD_PARMS = {"sky", "water", "fog", "trans", "nodraw", "alphashadow", "nolightmap_x", "slime", "lava"}


def material_for(stem):
    st = stem.lower().replace("\\", "/")
    if st.endswith(("_s", "_n", "_nh", "_h")):
        return None
    for mat, pat in RULES:
        if re.search(pat, st):
            return None if mat == "skip" else mat
    return None


# ---------------------------------------------------------------- asset lookup
def pack_list():
    return [p for p in PAKS if p.exists()] + [p for p in (HD, ZFIX) if p.exists()]


def collect_images(prefix="textures/"):
    """stem(lowercase) -> (pk, member); zfix wins over HD, HD over originals, later paks over earlier."""
    found = {}
    for pk in pack_list():
        with zipfile.ZipFile(pk) as z:
            for n in z.namelist():
                stem, dot, ext = n.rpartition(".")
                if dot and ext.lower() in ("tga", "jpg", "png") and n.lower().startswith(prefix):
                    found[stem.lower()] = (pk, n)
    return found


def tokenize(txt):
    txt = re.sub(r"//[^\n]*", "", txt)
    txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
    return re.findall(r'[{}]|"[^"]*"|[^\s{}]+', txt)


def parse_shaders():
    """name(lower) -> dict(parms=set, stages=[dict]) from all scripts/*.shader (later packs override)."""
    out = {}
    for pk in pack_list():
        with zipfile.ZipFile(pk) as z:
            for n in z.namelist():
                if not (n.lower().startswith("scripts/") and n.lower().endswith(".shader")):
                    continue
                tk = tokenize(z.read(n).decode("latin-1"))
                i = 0
                while i < len(tk):
                    name = tk[i].strip('"').lower()
                    if i + 1 < len(tk) and tk[i + 1] == "{":
                        i += 2
                        sh = {"parms": set(), "stages": [], "flags": set()}
                        depth, cur, line = 1, None, []
                        while i < len(tk) and depth:
                            t = tk[i]
                            if t == "{":
                                depth += 1
                                cur = {}
                            elif t == "}":
                                depth -= 1
                                if cur is not None:
                                    sh["stages"].append(cur)
                                    cur = None
                            else:
                                # a directive runs to the next keyword/brace; read it by keyword table
                                k = t.lower()
                                nxt = tk[i + 1] if i + 1 < len(tk) else ""
                                if cur is None:
                                    if k == "surfaceparm":
                                        sh["parms"].add(nxt.lower())
                                    elif k in ("deformvertexes", "polygonoffset", "q3map_sun", "qer_trans"):
                                        sh["flags"].add(k)
                                else:
                                    if k in ("map", "clampmap") and "map" not in cur:
                                        cur["map"] = nxt.lower()
                                    elif k == "animmap":
                                        cur["anim"] = True
                                    elif k in ("alphafunc", "blendfunc", "tcgen", "tcmod", "alphagen", "depthwrite"):
                                        cur.setdefault(k, []).append(nxt.lower())
                            i += 1
                        out[name] = sh
                    else:
                        i += 1
    return out


def resolve_diffuse(name, shaders):
    """BSP shader name -> diffuse texture stem (no extension), or None if it is not a plain opaque lit diffuse."""
    nm = name.lower().replace("\\", "/")
    sh = shaders.get(nm)
    if sh is None:
        return re.sub(r"\.(tga|jpg|png)$", "", nm)
    if sh["parms"] & BAD_PARMS or "deformvertexes" in sh["flags"] or "polygonoffset" in sh["flags"]:
        return None
    diff = [s for s in sh["stages"] if s.get("map") != "$lightmap"]
    # fake environment shine (tinfx, tcgen environment, one_minus_dst_alpha): rend2 drops it (r_codShaderCollapse)
    shine = [s for s in diff if s.get("tcgen", [""])[0] == "environment" and "tinfx" in s.get("map", "")
             and s.get("blendfunc", [""])[0] == "gl_one_minus_dst_alpha"]
    if shine and len(diff) == 2:
        diff = [s for s in diff if s not in shine]
    # ember underlay (opaque rotating glow) with the vertex-lit diffuse alpha-blended on top: rend2 lights the top stage
    elif (len(diff) == 2 and "ember" in diff[0].get("map", "") and "blendfunc" not in diff[0]
          and diff[1].get("blendfunc", [""])[0] == "blend"):
        diff = diff[1:]
    if len(diff) != 1:
        return None
    s = diff[0]
    if s.get("anim") or "alphafunc" in s or "tcgen" in s or "tcmod" in s or "map" not in s or s["map"].startswith("$"):
        return None
    bf = s.get("blendfunc", [""])[0]
    if bf and bf not in ("filter", "gl_dst_color", "blend") and not (shine and bf == "gl_one"):
        return None
    return re.sub(r"\.(tga|jpg|png)$", "", s["map"])


def all_maps():
    """SP map names in the paks (mp_* excluded), sorted."""
    names = set()
    for pk in PAKS:
        if pk.exists():
            with zipfile.ZipFile(pk) as z:
                names.update(m.group(1) for n in z.namelist() if (m := re.fullmatch(r"maps/([^/]+)\.bsp", n)))
    return sorted(n for n in names if not n.startswith("mp_"))


def bsp_shader_counts(mapname):
    b = None
    for pk in PAKS:  # later paks override earlier ones (sp_pak1-4 carry newer crypt1/dam/end)
        if not pk.exists():
            continue
        with zipfile.ZipFile(pk) as z:
            if f"maps/{mapname}.bsp" in z.namelist():
                b = z.read(f"maps/{mapname}.bsp")
    if b is None:
        sys.exit(f"map {mapname} not found in paks")
    lumps = [struct.unpack("<ii", b[8 + 8 * i:16 + 8 * i]) for i in range(17)]
    o, l = lumps[1]
    sh = [b[o + 72 * i:o + 72 * i + 64].split(b"\0")[0].decode("latin-1") for i in range(l // 72)]
    o, l = lumps[13]
    cnt = Counter()
    for i in range(l // 104):
        cnt[struct.unpack("<i", b[o + 104 * i:o + 104 * i + 4])[0]] += 1
    return [(s, cnt[i]) for i, s in enumerate(sh)]


def select(a):
    """-> rows (surfaces, class, stem, (pack, member)) ranked by surface count; --map all = union over every SP map
    (surface counts summed). Also fills select.maps: stem -> sorted map names."""
    select.maps = defaultdict(set)
    if a.models:
        # model skins (weapons etc.): normals only, the alpha height stays flat so parallax never runs on them
        imgs = collect_images("models/")
        rows = [(0, "model", s) for s in sorted(imgs) if re.search(a.models, s) and not s.endswith(("_s", "_n", "_nh", "_h"))]
        if a.exclude:
            rows = [r for r in rows if not re.search(a.exclude, r[2])]
        if a.models_opaque:
            # drop skins whose shader script is not a plain opaque lit diffuse (alpha-tested cards, blended overlays,
            # animated/scrolling, transparent, unlit): a normal map would be wrong or never used
            shaders = parse_shaders()
            def plain(stem):
                sh = shaders.get(stem)
                if sh is None:
                    return True
                if sh["parms"] & {"trans", "nolightmap"}:
                    return False
                st = sh["stages"]
                if any("alphafunc" in x for x in st):
                    # alpha-tested: fine when only a sliver is cut away (damage/gib masks on bodies), wrong for cards
                    pk, mem = imgs[stem]
                    with zipfile.ZipFile(pk) as z:
                        im = Image.open(io.BytesIO(z.read(mem)))
                    if "A" not in im.convert("RGBA").getbands() or np.mean(np.asarray(im.convert("RGBA"))[..., 3] < 128) > 0.15:
                        return False
                return not (st and any(k in st[0] for k in ("blendfunc", "anim", "tcgen", "tcmod", "alphagen")))
            rows = [r for r in rows if plain(r[2])]
        return [(n, m, s, imgs[s]) for n, m, s in rows]
    imgs = collect_images()
    if a.map:
        shaders = parse_shaders()
        maps = all_maps() if a.map == "all" else [a.map]
        tot, cls = Counter(), {}
        for mp in maps:
            for name, n in bsp_shader_counts(mp):
                stem = resolve_diffuse(name, shaders)
                if stem is None or stem not in imgs:
                    continue
                m = material_for(stem)
                if m:
                    tot[stem] += n
                    cls[stem] = m
                    select.maps[stem].add(mp)
        rows = sorted(((n, cls[s], s) for s, n in tot.items()), key=lambda r: (-r[0], r[2]))
    else:
        rows = [(0, material_for(s), s) for s in sorted(imgs) if material_for(s)]
    if a.only:
        rows = [r for r in rows if re.search(a.only, r[2])]
    if a.max:
        rows = rows[:a.max]
    return [(n, m, s, imgs[s]) for n, m, s in rows]


# ---------------------------------------------------------------- maths
def load_albedo(pk, member, max_side=MAX_SIDE):
    with zipfile.ZipFile(pk) as z:
        img = Image.open(io.BytesIO(z.read(member)))
        img.load()
    img = img.convert("RGB")
    if max(img.size) > max_side:
        s = max_side / max(img.size)
        img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    return np.asarray(img, np.float32) / 255.0


_sess = None
def local_normalise(gray, sigma_frac, eps, pre_blur=1.0):
    """CLAHE-style local contrast normalisation of a grey image, periodic (FFT blur, so tileable stays tileable).
    Subtracts the local mean and divides by the local std (+eps so featureless areas are not blown up to noise), after
    a ~1 px blur that removes quantisation/JPEG speckle (dark textures only have a handful of grey levels)."""
    g = periodic_blur(gray.astype(np.float64), pre_blur) if pre_blur > 0 else gray.astype(np.float64)
    s = sigma_frac * min(g.shape)
    d = g - periodic_blur(g, s)
    sd = np.sqrt(np.maximum(periodic_blur(d * d, s), 0))
    out = d / (sd + eps)
    return np.clip(0.5 + 0.22 * out, 0, 1).astype(np.float32)


def brighten(rgb, a):
    """Exposure-lift dark albedo before the relief stats and DeepBump see it (only the _nh map is derived from it, the
    shown diffuse is untouched): linear gain bright_target / mean luma, capped at bright_max, clipped to 1."""
    if a.bright_target <= 0:
        return rgb
    luma = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    m = float(luma.mean())
    if m >= a.bright_target:
        return rgb
    gain = min(a.bright_target / max(m, 1e-4), a.bright_max)
    return np.clip(rgb * gain, 0, 1).astype(np.float32)


def texture_stats(rgb, a):
    """mean luma, luma std after a mild blur, 5-95 range, and a 0..1 confidence that the albedo carries real relief."""
    luma = (rgb @ np.array([0.299, 0.587, 0.114], np.float32)).astype(np.float64)
    b = periodic_blur(luma, 1.5)
    rng = float(np.subtract(*np.percentile(b, (95, 5))))
    conf = float(np.clip((rng - a.conf_lo) / max(a.conf_hi - a.conf_lo, 1e-6), 0, 1))
    return {"mean": float(luma.mean()), "std": float(b.std()), "range": rng, "conf": conf}


def deepbump_normals(rgb, overlap=64, autolevel=False, norm=None):
    """Overlapping 256 tiles over a wrap-padded image, tent-weighted blend. Returns (H,W,3) unit normals (y up)."""
    global _sess
    if _sess is None:
        if not MODEL.exists():
            sys.exit(f"missing {MODEL}; download {MODEL_URL}")
        import onnxruntime as ort
        ort.disable_telemetry_events()
        so = ort.SessionOptions()
        if THREADS:
            so.intra_op_num_threads = THREADS
            so.inter_op_num_threads = 1
        _sess = ort.InferenceSession(str(MODEL), so, providers=["CPUExecutionProvider"])
    gray = rgb.mean(axis=2)
    if autolevel:  # dark, low-contrast albedo makes the model hallucinate noise: stretch the model input only
        lo, hi = np.percentile(gray, (1, 99))
        gray = np.clip((gray - lo) / max(hi - lo, 0.08), 0, 1)
    if norm is not None:
        gray = local_normalise(gray, *norm)
    H, W = gray.shape
    pad = overlap
    g = np.pad(gray, ((pad, pad), (pad, pad)), mode="wrap")
    # make sure the canvas holds at least one tile
    ph, pw = max(0, TILE - g.shape[0]), max(0, TILE - g.shape[1])
    if ph or pw:
        g = np.pad(g, ((0, ph), (0, pw)), mode="wrap")
    Hp, Wp = g.shape
    stride = TILE - overlap
    ys = list(range(0, Hp - TILE + 1, stride))
    xs = list(range(0, Wp - TILE + 1, stride))
    if ys[-1] != Hp - TILE: ys.append(Hp - TILE)
    if xs[-1] != Wp - TILE: xs.append(Wp - TILE)
    ramp = np.minimum(np.arange(TILE) + 1, np.arange(TILE)[::-1] + 1).astype(np.float32)
    win = np.minimum(np.outer(ramp, ramp), overlap * overlap) + 1e-3
    acc = np.zeros((3, Hp, Wp), np.float32)
    wsum = np.zeros((Hp, Wp), np.float32)
    for y in ys:
        for x in xs:
            t = g[y:y + TILE, x:x + TILE][None, None].astype(np.float32)
            p = _sess.run(None, {"input": t})[0][0]
            acc[:, y:y + TILE, x:x + TILE] += p * win
            wsum[y:y + TILE, x:x + TILE] += win
    acc /= wsum
    n = acc[:, pad:pad + H, pad:pad + W].transpose(1, 2, 0)
    n = n / np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
    return n


def freqs(h, w):
    ky = np.fft.fftfreq(h)[:, None] * 2 * np.pi
    kx = np.fft.fftfreq(w)[None, :] * 2 * np.pi
    return kx, ky


def integrate(n, flip):
    """Frankot-Chellappa: slopes from normals -> periodic height (pixel units)."""
    nz = np.maximum(n[..., 2], 0.35)
    sx = -n[..., 0] / nz                  # dh/dcol
    sy = n[..., 1] / nz * (-1 if flip else 1)   # dh/drow (image y is down, normal y is up)
    kx, ky = freqs(*sx.shape)
    den = kx * kx + ky * ky
    den[0, 0] = 1
    H = (-1j * kx * np.fft.fft2(sx) - 1j * ky * np.fft.fft2(sy)) / den
    H[0, 0] = 0
    return np.fft.ifft2(H).real, kx, ky


def fft_filter(a, kx, ky, f):
    return np.fft.ifft2(np.fft.fft2(a) * f(kx * kx + ky * ky)).real


def periodic_blur(a, sigma):
    kx, ky = freqs(*a.shape)
    return fft_filter(a, kx, ky, lambda k2: np.exp(-0.5 * k2 * sigma * sigma))


def highpass(a, wavelength):
    kx, ky = freqs(*a.shape)
    s = wavelength / (2 * np.pi)
    return fft_filter(a, kx, ky, lambda k2: 1 - np.exp(-0.5 * k2 * s * s))


def plateau(h, p_lo, p_hi):
    lo, hi = np.percentile(h, (p_lo, p_hi))
    return np.clip((h - lo) / max(hi - lo, 1e-9), 0, 1), hi - lo


def normals_from_height(h01, relief_px, flip):
    """rend2 tangent space: bitangent = +t = image down. Slope of height (pixels) -> normal, stored 0..255."""
    z = h01 * relief_px
    dx = (np.roll(z, -1, 1) - np.roll(z, 1, 1)) * 0.5
    dy = (np.roll(z, -1, 0) - np.roll(z, 1, 0)) * 0.5
    nx, ny = -dx, (dy if flip else -dy)
    inv = 1 / np.sqrt(nx * nx + ny * ny + 1)
    return np.dstack([nx * inv, ny * inv, inv])


def seam_stats(arr):
    """mean |opposite-edge diff| vs mean |neighbouring-pixel diff| for HxWxC float arr in 8-bit levels."""
    a = arr.astype(np.float32)
    wrap = (np.abs(a[:, 0] - a[:, -1]).mean() + np.abs(a[0] - a[-1]).mean()) / 2
    nb = (np.abs(a[:, 1:] - a[:, :-1]).mean() + np.abs(a[1:] - a[:-1]).mean()) / 2
    return wrap, nb


def bake(rgb, a, force_flat=False, n=None, normals_only=False, rel_scale=1.0):
    H, W = rgb.shape[:2]
    luma = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    info = {}
    if a.legacy_luma:
        lo, hi = np.percentile(luma, (2, 98))
        h01 = np.clip((luma - lo) / max(hi - lo, 1e-3), 0, 1)
        relief = a.relief * max(H, W)
        raw = h01
    else:
        st = texture_stats(rgb, a)
        info["stats"] = st
        use_norm = a.dark_norm == "on" or (a.dark_norm == "auto" and (st["mean"] < a.dark_mean or st["range"] < a.dark_range))
        info["normed"] = use_norm
        if n is None:
            n = deepbump_normals(rgb, autolevel=a.autolevel, norm=(a.ln_sigma, a.ln_eps) if use_norm else None)
        n = n.astype(np.float32)
        hpx, kx, ky = integrate(n, a.flip_y)
        hpx = highpass(hpx, a.highpass * min(H, W))
        # modest albedo detail (mortar lines): luma high-pass scaled to the same std, mixed in
        ld = highpass(luma.astype(np.float64), a.highpass * min(H, W))
        ld = ld / max(ld.std(), 1e-9) * hpx.std()
        raw = hpx + a.luma_mix * ld
        # fine field (normals) and smooth field (parallax ray march): the same plateau mapping, the smooth one is
        # low-passed first so the 75-95th percentile plateau still holds after blurring
        fine, rng = plateau(raw, a.p_lo, a.p_hi)
        fine = np.clip(periodic_blur(fine, 0.7), 0, 1)
        if a.height_blur > 0:
            sigma = a.height_blur * min(H, W)
            smooth, rng = plateau(periodic_blur(raw, sigma), a.p_lo, a.p_hi)
            h01 = smooth
            nh = smooth + a.normal_detail * (fine - periodic_blur(fine, sigma))
        else:
            h01 = nh = fine
        info["rng_px"] = rng
        relief = float(np.clip(rng * a.strength, 0.01 * max(H, W), 0.04 * max(H, W)))
        # coherence: share of the raw height's energy that survives a blur (noise lives at high frequency)
        sg = 0.02 * min(H, W)
        info["coh"] = float(periodic_blur(raw, sg).std() / max(raw.std(), 1e-9))
        conf = st["conf"]
        if a.coh_gate:
            term = float(np.clip((info["coh"] - a.coh_lo) / max(a.coh_hi - a.coh_lo, 1e-6), 0, 1))
            conf *= a.coh_floor + (1 - a.coh_floor) * term
        # spikiness: mean |Laplacian| of the alpha height per unit std, scaled by texture size. Clean relief is ~7-16,
        # shredded high-frequency noise (bark, noisy wood strips) 24-30
        lap0 = float(np.abs(4 * h01 - np.roll(h01, 1, 0) - np.roll(h01, -1, 0) - np.roll(h01, 1, 1) - np.roll(h01, -1, 1)).mean())
        info["spike"] = lap0 * min(H, W) / max(float(h01.std()), 1e-6)
        conf *= float(np.clip((a.spike_hi - info["spike"]) / max(a.spike_hi - a.spike_lo, 1e-6), 0, 1))
        if force_flat:
            conf = 0.0
        info["conf"] = conf
        # confidence gating: low confidence -> alpha height blends toward the flat plateau (1.0), normal relief shrinks
        k = float(np.clip(conf / a.conf_gate, 0, 1)) if a.conf_gate > 0 else 1.0
        info["gate"] = k
        info["flat"] = k < a.flat_below
        info["lap_raw"] = float(np.abs(4 * h01 - np.roll(h01, 1, 0) - np.roll(h01, -1, 0) - np.roll(h01, 1, 1) - np.roll(h01, -1, 1)).mean() * 255)
        h01 = 1 - (1 - h01) * (0.0 if normals_only else k)
        nh = 1 - (1 - nh) * (a.soft_floor + (1 - a.soft_floor) * k)
        raw = (raw - raw.min()) / max(np.ptp(raw), 1e-9)
    if a.legacy_luma:
        nh = h01
        info.update(spike=0.0, conf=1.0, gate=1.0, flat=False, coh=1.0, lap_raw=0.0, normed=False, stats=texture_stats(rgb, a))
    relief *= rel_scale
    info["relief_px"] = relief
    info["pct"] = dict(zip((1, 5, 25, 50, 75, 90, 95, 99), np.percentile(raw, (1, 5, 25, 50, 75, 90, 95, 99)).round(3)))
    info["at1"] = float((h01 >= 0.999).mean())
    info["mean"] = float(h01.mean())
    info["lap"] = float(np.abs(4 * h01 - np.roll(h01, 1, 0) - np.roll(h01, -1, 0) - np.roll(h01, 1, 1) - np.roll(h01, -1, 1)).mean() * 255)
    nrm = normals_from_height(nh, relief, a.flip_y)
    out = np.dstack([(nrm * 0.5 + 0.5) * 255, h01 * 255])
    out8 = np.clip(out + 0.5, 0, 255).astype(np.uint8)
    info["seam_wrap"], info["seam_nb"] = seam_stats(out8)
    info["seam_wrap_h"], info["seam_nb_h"] = seam_stats(out8[..., 3:])
    info["seam_albedo"] = seam_stats(rgb * 255)
    info["luma_corr"] = float(np.corrcoef(h01.ravel(), luma.ravel())[0, 1])
    return out8, info


def contact_sheet(items, path, cell=192):
    sheet = Image.new("RGB", (cell * 3 + 4, len(items) * (cell + 2)), (30, 30, 30))
    for r, (stem, rgb, out8) in enumerate(items):
        ims = [Image.fromarray((rgb * 255).astype(np.uint8)), Image.fromarray(out8[..., :3]), Image.fromarray(out8[..., 3])]
        for c, im in enumerate(ims):
            sheet.paste(im.convert("RGB").resize((cell, cell), Image.LANCZOS), (c * (cell + 2), r * (cell + 2)))
        d = ImageDraw.Draw(sheet)
        d.rectangle((0, r * (cell + 2), cell, r * (cell + 2) + 10), fill=(0, 0, 0))
        d.text((2, r * (cell + 2)), stem.split("/", 1)[-1][-34:], fill=(255, 255, 0))
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "run/codmod/codmod_height.pk3"))
    ap.add_argument("--map", help="only textures used by this map (e.g. escape1), ranked by surface count; 'all' = every SP map")
    ap.add_argument("--models", help="regex on model skin paths (models/...): bake normals-only maps for those instead of world textures, e.g. 'weapons2/(colt|luger)/'")
    ap.add_argument("--exclude", help="--models only: regex on the skin path to drop")
    ap.add_argument("--models-opaque", action="store_true", help="--models only: drop skins whose shader is alpha-tested (more than 15%% of texels cut), blended, animated or unlit")
    ap.add_argument("--preset", choices=sorted(PRESETS), help="model pack as shipped (fills --models/--exclude/--models-opaque/--out unless given);")
    ap.add_argument("--only", help="regex on the texture path")
    ap.add_argument("--max", type=int, default=36, help="cap (0 = no cap; --map all usually wants 0)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--preview", nargs="?", const=str(HERE / "preview/contact.png"), help="write a contact sheet PNG")
    ap.add_argument("--legacy-luma", action="store_true", help="old luma-from-diffuse heights (A/B reference)")
    ap.add_argument("--p-lo", type=float, default=0.5, help="percentile mapped to height 0")
    ap.add_argument("--p-hi", type=float, default=85.0, help="percentile mapped to height 1 (plateau)")
    ap.add_argument("--luma-mix", type=float, default=0.35)
    ap.add_argument("--highpass", type=float, default=0.12, help="high-pass cutoff wavelength, fraction of texture size")
    ap.add_argument("--height-blur", type=float, default=0.02, help="blur sigma of the alpha (parallax) height, fraction of texture size (0 = off)")
    ap.add_argument("--normal-detail", type=float, default=0.6, help="how much fine (un-blurred) height detail goes into the RGB normal")
    ap.add_argument("--strength", type=float, default=0.8, help="multiplier on the natural relief (pixels)")
    ap.add_argument("--relief", type=float, default=0.03, help="legacy-luma relief, fraction of texture size")
    ap.add_argument("--conf-lo", type=float, default=0.08, help="5-95 luma range (0..1, after 1.5px blur) giving confidence 0")
    ap.add_argument("--conf-hi", type=float, default=0.20, help="5-95 luma range giving confidence 1")
    ap.add_argument("--flatten", default=DEFAULT_FLATTEN, help="regex on the texture path: force these textures flat (no parallax, soft normals); '' = none")
    ap.add_argument("--conf-gate", type=float, default=0.6, help="confidence at/above which the full relief is kept; below it relief scales linearly to flat (0 = gating off)")
    ap.add_argument("--flat-below", type=float, default=0.15, help="gate factor below which a texture is reported as flattened")
    ap.add_argument("--soft-floor", type=float, default=0.2, help="share of the RGB-normal relief kept when the height is fully flattened")
    ap.add_argument("--no-coh-gate", dest="coh_gate", action="store_false", help="ignore the height-coherence term in the confidence")
    ap.add_argument("--spike-lo", type=float, default=16.0, help="height spikiness (see bake) at/below which confidence is untouched")
    ap.add_argument("--spike-hi", type=float, default=26.0, help="height spikiness at/above which confidence is 0")
    ap.add_argument("--coh-floor", type=float, default=0.4, help="confidence multiplier at zero coherence (fine carved detail is coherent-poor but fine)")
    ap.add_argument("--coh-lo", type=float, default=0.25, help="coherence (low-pass/raw height std) giving confidence 0")
    ap.add_argument("--coh-hi", type=float, default=0.5, help="coherence giving full confidence")
    ap.add_argument("--dark-norm", choices=("auto", "on", "off"), default="off", help="local contrast normalisation of the DeepBump input (auto = dark/low-contrast textures only; off by default: it did not measurably help)")
    ap.add_argument("--dark-mean", type=float, default=0.12, help="auto norm: mean luma below this")
    ap.add_argument("--dark-range", type=float, default=0.12, help="auto norm: 5-95 luma range below this")
    ap.add_argument("--ln-sigma", type=float, default=0.06, help="local normalisation window sigma, fraction of texture size")
    ap.add_argument("--ln-eps", type=float, default=0.015, help="local normalisation std floor (stops featureless areas turning into noise)")
    ap.add_argument("--bright-target", type=float, default=0.30, help="lift textures darker than this mean luma (0..1) to it before stats + DeepBump (0 = off); only the _nh map sees the lift")
    ap.add_argument("--bright-max", type=float, default=4.0, help="maximum gain of --bright-target")
    ap.add_argument("--autolevel", action="store_true", help="contrast-stretch the grey fed to DeepBump (mixed results on dark textures)")
    ap.add_argument("--flip-y", action="store_true", help="flip the green channel convention")
    ap.add_argument("--max-side", type=int, default=MAX_SIDE, help="cap on the longest side of the diffuse used for DeepBump and the output (px)")
    ap.add_argument("--jobs", type=int, default=0, help="worker processes (0 = cores/4)")
    ap.add_argument("--threads", type=int, default=0, help="onnxruntime threads per worker (0 = cores/jobs)")
    ap.add_argument("--no-cache", action="store_true", help="ignore and overwrite the cache")
    ap.add_argument("--pack-only", action="store_true", help="only write the pk3 from the cache (skip missing textures)")
    a = ap.parse_args()
    if a.preset:
        pm, pe, po, pout = PRESETS[a.preset]
        a.models = a.models or pm
        a.exclude = a.exclude or pe
        a.models_opaque = a.models_opaque or po
        if a.out == ap.get_default("out"):
            a.out = str(ROOT / pout)
    global THREADS
    ncpu = os.cpu_count() or 4
    if a.jobs <= 0:
        a.jobs = max(1, ncpu // 4)
    THREADS = a.threads or max(1, ncpu // a.jobs)
    if a.legacy_luma and a.out.endswith("codmod_height.pk3"):
        a.out = a.out.replace("codmod_height", "codmod_height_legacy")
    sel = select(a)
    if a.list:
        for n, m, s, (pk, mem) in sel:
            st = texture_stats(load_albedo(pk, mem, a.max_side), a)
            print(f"{m:9s} {n:5d} conf {st['conf']:.2f} mean {st['mean']:.3f} range {st['range']:.3f} {s}   <- {pk.name} [{','.join(sorted(select.maps[s])) if a.map == 'all' else ''}]")
        print(f"{len(sel)} textures")
        return

    # ---- bake (incremental: one cache entry per texture, keyed by source + parameters)
    t0 = time.time()
    jobs = [(m, stem, pk, member, bool(a.flatten and re.search(a.flatten, stem))) for n, m, stem, (pk, member) in sel]
    todo = [j for j in jobs if a.no_cache or not entry_ok(a, j)]
    if a.pack_only:
        todo = []
    print(f"{len(jobs)} textures, {len(jobs) - len(todo)} cached, {len(todo)} to bake ({a.jobs} workers x {THREADS} threads)", flush=True)
    done = 0
    if todo:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(a.jobs, initializer=init_worker, initargs=(THREADS,)) as ex:
            futs = [ex.submit(bake_job, a, j) for j in todo]
            for f in as_completed(futs):
                done += 1
                print(f"[{done}/{len(todo)} {time.time() - t0:.0f}s] " + f.result(), flush=True)
    rows = []
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as zo:
        for m, stem, pk, member, ff in jobs:
            png, js = entry_paths(a, (m, stem, pk, member, ff))
            if not png.exists():
                continue
            zo.writestr(f"{stem}_nh.png", png.read_bytes())
            info = json.loads(js.read_text())
            info["stem"], info["cls"] = stem, m
            rows.append(info)
    if rows:
        for r in rows:
            print(f"{r['stem']} {r['w']}x{r['h']} [{r['cls']}] conf {r['stats_conf']:.2f} coh {r['coh']:.2f} spike {r['spike']:.1f} -> {r['conf']:.2f} gate {r['gate']:.2f}"
                  f"{' FLAT' if r['flat'] else ''} relief {r['relief_px']:.1f}px lap {r['lap']:.2f} luma-corr {r['luma_corr']:+.2f}")
        print("mean |laplacian| of alpha (8-bit levels): {:.3f}, mean at1.0: {:.1f}%".format(np.mean([r['lap'] for r in rows]), 100 * np.mean([r['at1'] for r in rows])))
        flat = [r["stem"] for r in rows if r["flat"]]
        soft = [r["stem"] for r in rows if not r["flat"] and r["gate"] < 1]
        print(f"flattened (gate < {a.flat_below}): {len(flat)} of {len(rows)}: " + ", ".join(flat))
        print(f"partially reduced: {len(soft)}: " + ", ".join(f"{x} ({next(r['gate'] for r in rows if r['stem'] == x):.2f})" for x in soft))
        print(f"wrote {len(rows)} height maps to {a.out} ({Path(a.out).stat().st_size / 1e6:.1f} MB), {time.time() - t0:.0f}s")
        print("mean seam ratio wrap/neighbour: rgb {:.2f} height {:.2f}".format(
            np.mean([r['seam_wrap'] / r['seam_nb'] for r in rows]), np.mean([r['seam_wrap_h'] / max(r['seam_nb_h'], 1e-6) for r in rows])))
    if a.preview and rows:
        Path(a.preview).parent.mkdir(parents=True, exist_ok=True)
        by = {j[1]: j for j in jobs}
        items = []
        for r in rows:
            j = by[r["stem"]]
            out8 = np.asarray(Image.open(entry_paths(a, j)[0]).convert("RGBA"))
            items.append((r["stem"], load_albedo(j[2], j[3], a.max_side), out8))
        for i in range(0, len(items), 6):
            p = Path(a.preview).with_name(Path(a.preview).stem + (f"_{i // 6 + 1}" if len(items) > 6 else "") + ".png")
            contact_sheet(items[i:i + 6], p)
            print("preview:", p)


# ---------------------------------------------------------------- cache + workers
# Cache layout (tools/height-bake/cache, git-ignored): nrm/<key>.npy = DeepBump normals (float16, the slow part, depends
# only on the source image and the DeepBump input options); nh/<key>.png + .json = final RGBA map and its stats (depends
# on all bake parameters). Retuning the gate/blur/plateau therefore only redoes the cheap FFT part.
NONKEY = {"preset", "out", "map", "models", "only", "max", "list", "preview", "jobs", "threads", "no_cache", "pack_only", "flatten", "exclude", "models_opaque"}


def _h(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def src_id(pk, member):
    st = pk.stat()
    return [pk.name, member, st.st_size, int(st.st_mtime)]


def nrm_key(a, j):
    return _h(VERSION, src_id(j[2], j[3]), a.max_side, a.autolevel, a.dark_norm, a.dark_mean, a.dark_range, a.ln_sigma, a.ln_eps)


def nh_key(a, j):
    prm = {k: v for k, v in vars(a).items() if k not in NONKEY}
    return _h(VERSION, src_id(j[2], j[3]), prm, j[4], CLASS_STRENGTH.get(j[0]))


def entry_paths(a, j):
    d = CACHE / "nh"
    base = j[1].replace("/", "__") + "." + nh_key(a, j)
    return d / (base + ".png"), d / (base + ".json")


def entry_ok(a, j):
    png, js = entry_paths(a, j)
    return png.exists() and js.exists()


def init_worker(threads):
    global THREADS
    THREADS = threads


def bake_job(a, j):
    m, stem, pk, member, ff = j
    t = time.time()
    rgb = brighten(load_albedo(pk, member, a.max_side), a)
    npath = CACHE / "nrm" / (stem.replace("/", "__") + "." + nrm_key(a, j) + ".npy")
    n = None
    if npath.exists() and not a.no_cache:
        n = np.load(npath)
    elif not a.legacy_luma:
        st = texture_stats(rgb, a)
        use_norm = a.dark_norm == "on" or (a.dark_norm == "auto" and (st["mean"] < a.dark_mean or st["range"] < a.dark_range))
        n = deepbump_normals(rgb, autolevel=a.autolevel, norm=(a.ln_sigma, a.ln_eps) if use_norm else None)
        npath.parent.mkdir(parents=True, exist_ok=True)
        np.save(npath, n.astype(np.float16))
    out8, info = bake(rgb, a, ff, n, m in NORMALS_ONLY, CLASS_STRENGTH.get(m, 1.0))
    png, js = entry_paths(a, j)
    png.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    Image.fromarray(out8, "RGBA").save(buf, "PNG", optimize=False)
    info["pct"] = {str(k): float(v) for k, v in info["pct"].items()}
    info["w"], info["h"] = rgb.shape[1], rgb.shape[0]
    info["stats_conf"] = info["stats"]["conf"]
    info["seam_albedo"] = list(info["seam_albedo"])
    tp, tj = png.with_name(png.name + ".tmp"), js.with_name(js.name + ".tmp")
    tp.write_bytes(buf.getvalue())
    tj.write_text(json.dumps(info, default=float))
    tp.replace(png)       # png first, json last: entry_ok needs both
    tj.replace(js)
    return f"{stem} {rgb.shape[1]}x{rgb.shape[0]} [{m}] gate {info['gate']:.2f}{' FLAT' if info['flat'] else ''} ({time.time() - t:.0f}s)"


if __name__ == "__main__":
    sys.exit(main())
