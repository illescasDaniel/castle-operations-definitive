# height-bake: AI normal+height maps for the parallax shader (experiment)

Bakes rend2 `<texture>_nh.png` (rgb = tangent-space normal, alpha = height) for wall/floor textures into
`run/codmod/codmod_height.pk3`. rend2 (`tr_shader.c`) appends `_nh` to the diffuse base name and enables parallax when
the file has alpha and `r_parallaxMapping` is on. Derived from RTCW textures: git-ignored, never redistribute.
Source priority as in spec-bake: `codmod_zfix.pk3` > `codmod_hd.pk3` > game paks; downscaled to `--max-side` (default 1024).

Why not luma heights: darkness is not depth, so the whole surface sank and props floated (see `--legacy-luma`).

## Setup (once)

```bash
cd tools/height-bake
python3 -m venv .venv && .venv/bin/pip install numpy pillow onnxruntime
mkdir -p models && curl -L -o models/deepbump256.onnx https://github.com/HugoTini/DeepBump/raw/master/deepbump256.onnx
```

Model: DeepBump `deepbump256.onnx` (GPLv3, 26.7 MB, sha256 3a2ababc...4d67). `.venv/`, `models/`, `preview/`, `cache/` are git-ignored.

## Full game (all SP maps)

```bash
tools/height-bake/.venv/bin/python -I tools/height-bake/height_bake.py --map all --max 0 > tools/height-bake/preview/all.log
```

`--map all` unions the textures of every SP map in the paks (assault, baseout, boss1/2, castle, chateau, church,
crypt1/2, cutscene1/6/9/11/14/19, dam, dark, dig, end, escape1/2, factory, forest, norway, rocket, sfm, swf, trainyard,
tram, village1/2, xlabs; later paks override earlier ones, `mp_*` excluded), sums the surface counts and bakes each
texture once: 293 textures (152 brick/stone, 74 wood, 36 concrete, 28 floor, 3 rock), one pack
`run/codmod/codmod_height.pk3` (142 MB, 1024 max, most textures are 512 or smaller anyway). `--list` shows the maps
using each texture. Full cold bake: about 30 s on 32 cores (8 workers x 4 onnx threads; `--jobs`, `--threads`).

Incremental: every texture is cached in `cache/` (git-ignored, ~0.6 GB): DeepBump normals (`nrm/`, the slow part, keyed
by source file + `--max-side` + DeepBump input options) and the final map + stats (`nh/`, keyed by source + all bake
parameters + flatten). Interrupting and rerunning continues where it stopped; retuning gate/blur/plateau only redoes
the fast FFT stage; the pk3 is always written from the cache at the end (`--pack-only` skips baking, `--no-cache`
rebuilds). `--max-side 512` was tried for sizing: not needed (142 MB is far under 300 MB, only 38 textures are bigger
than 512), and it changes the confidence of a few textures.

Full-set gate result (escape1-tuned thresholds unchanged): 72 of 293 flattened (25%), 127 partially reduced. Flattened
are the dark wood, dark concrete (xconcrete_*, concrete_*), dark crypt/castle floors and c31 stone. `DEFAULT_FLATTEN`
(`xfloor_c03b|bricktrim_c06`, overridable with `--flatten`) forces two textures flat that gate as good but look wrong:
the xlab tile floor (every tile becomes a pillow) and the chateau trim (striped normals). Contact sheets of any subset:
`... --map all --max 0 --only '^textures/x$|^textures/y$' --out /tmp/x.pk3 --preview preview/sheet.png`
(rows are labelled with the texture name).

## Use

```bash
tools/height-bake/.venv/bin/python -I tools/height-bake/height_bake.py --map escape1 --list      # what would be baked
tools/height-bake/.venv/bin/python -I tools/height-bake/height_bake.py --map escape1 --preview   # bake + contact sheets
... --only 'castle_c31|floor_c10'      # regex on the texture path (works with or without --map)
... --legacy-luma                       # old luma heights, writes codmod_height_legacy.pk3 (A/B; do not load both)
```

`--map` reads the BSP shader lump, resolves shader scripts (skips alpha-tested, blended, animated, tcgen/tcmod, sky,
water, fog, deformVertexes, polygonOffset shaders) and ranks the wall/floor/wood/rock textures by surface count;
`--max` (default 36, 0 = no cap) caps it. Classes live in `RULES` at the top of the script. `--preview [path]` writes contact
sheets (albedo | normal | height, 6 rows each) to `preview/`. Tuning: `--p-hi` (plateau percentile, 85), `--p-lo`,
`--luma-mix` (0.35), `--height-blur` (0.02: Gaussian sigma of the alpha height as fraction of texture size, 0 = off),
`--normal-detail` (0.6: share of the fine, un-blurred height detail kept in the RGB normal), `--highpass` (cutoff wavelength as fraction of size, 0.12), `--strength` (0.8), `--flip-y`, `--autolevel`.

## Confidence gating (dark / low-contrast / noisy textures)

DeepBump hallucinates fine structure from near-featureless input and the plateau normalisation then stretches it to
full relief (shredded parallax on very dark stone and wood). Each texture gets a confidence 0..1, printed in the log
(`luma mean/std/range ... conf coh spike -> final conf gate`) and as a `--list` column:

- contrast: 5-95 luma range after a 1.5 px blur, `--conf-lo` 0.08 (conf 0) to `--conf-hi` 0.20 (conf 1);
- coherence: share of raw height energy surviving a blur, mild multiplier (`--coh-lo/--coh-hi`, floor `--coh-floor` 0.4;
  `--no-coh-gate` disables it);
- spikiness: mean |Laplacian| of the alpha per unit std, times texture size; clean relief 7-16, shredded noise 24-30
  (`--spike-lo` 16 .. `--spike-hi` 26 -> multiplier 1..0).

Gate factor k = conf / `--conf-gate` (0.6, clamped to 1). Alpha = 1 - (1 - alpha) * k (blend toward the flat plateau);
the RGB normal relief scales by `--soft-floor` (0.2) + (1 - 0.2) * k. k < `--flat-below` (0.15) is reported as FLAT. The log ends with the list of
flattened and partially reduced textures. `--conf-gate 0` turns gating off.

Local contrast normalisation of the DeepBump input (`--dark-norm on|auto|off`, `--ln-sigma`, `--ln-eps`) was tried and
left OFF by default: on the dark textures it lowered height coherence and made stone more fragmented (door_c17 got worse);
it only reduced noise on the narrow wood strips, which are flattened anyway. Escape1 numbers: mean alpha Laplacian
2.00 -> 0.65, 9 of 36 textures flattened (mostly dark wood, c31, floor_c10_a, bark strip), 13 partly reduced.

## Pipeline

1. DeepBump on the grey albedo, 256 tiles, 64 px overlap, tent-weighted blend, on a wrap-padded canvas (tiles seamless).
2. Frankot-Chellappa FFT integration of the slopes (periodic), high-pass, plus 35% albedo-luma high-pass (mortar lines).
3. Plateau: percentile 0.5 maps to 0, percentile 85 to 1.0 and everything above is clamped, so the stone tops sit on
   the geometric plane and only mortar/gaps sink. Light 0.7 px blur against stair-stepped ray marching.
3b. Two fields: the ALPHA height (parallax ray march) is the raw height blurred by `--height-blur` and then plateaued (so
   thin noise spikes are gone and the 85th percentile still sits at 1.0); the RGB normal comes from that smooth height
   plus `--normal-detail` of the fine detail, so lighting keeps small bumps while the ray march sees only large relief.
   Alpha roughness (mean |Laplacian|, 8-bit) is printed; escape1: 10.9 unblurred -> 4.3 at 0.01.
4. Normals recomputed from the final height (relief clamped to 1.2-5% of the texture size), stored with height in alpha.

The printed stats per texture: raw height percentiles, share of texels at 1.0, relief in pixels, correlation with luma
(must be positive: height convention check) and the seam check (mean abs diff between opposite edges vs between
neighbouring texels, 8-bit levels, plus the same for the albedo itself).

## Known limits

- Seams: the maths is periodic. A synthetic seamless albedo gives wrap/neighbour of about 0.9 in height. Many RTCW
  textures are not seamless themselves (albedo wrap diff is often 2-10x its neighbour diff) and the height inherits that.
- Very dark, low-contrast albedo (some wood, dark stone) gives noisy DeepBump output; those textures are flattened by the confidence gate rather than fixed (input normalisation did not help). Moss-like blotchy textures with good contrast (castle_c47) are only partly detected.
- Green channel convention is derived from rend2's tangent space (bitangent = +t = image down) and needs an in-game
  check; if bricks look dented instead of raised under side light, pass `--flip-y`.
