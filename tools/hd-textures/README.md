# hd-textures — local AI upscale for RTCW SP

Upscales Return to Castle Wolfenstein **single-player** textures from your owned
Steam `.pk3` files. The **script is shareable**; the **upscaled images are not**.

Do **not** commit or redistribute `codmod_hd.pk3` or anything under `samples/`.
Those are derivatives of proprietary id/Activision assets. Everyone re-runs this
tool against their own install.

## Requirements

- Python 3.11+ and [uv](https://github.com/astral-sh/uv)
- NVIDIA GPU + working CUDA (pilot/batch **require** CUDA unless `--allow-cpu`)
- Steam RTCW `Main/` with `pak0.pk3`, `sp_pak1.pk3`, `sp_pak2.pk3`

Default data path (override with `--data` or `RTCW_DATA`):

`~/.local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main`

## Setup

```bash
cd tools/hd-textures
uv sync
```

## Generate the current texture pack (recommended)

Current choice: **world textures `general-wdn` at 2×** with the anti-halo settings, which are the defaults (`--blend 0.85 --ring-clamp 0.02 --ring-radius 1 --downsample box`, see "Gentle world textures" below), **fonts `general-wdn` at 4×**, JPEG quality **90**.

Weights: [`realesr-general-wdn-x4v3.pth`](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth) from [Real-ESRGAN v0.2.5.0](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0) by [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — excellent upscaler; credit to the authors.

Font atlases (`fonts/**` and `menu/art/font*`) use the same WDN weights at native 4× (tried UltraSharp / animevideov3 first). Glyph `.dat` files stay vanilla (UVs are normalized).

From the repo root (after `scripts/setup.sh` so `run/codmod/` exists):

```bash
cd tools/hd-textures
uv sync

uv run hd-textures batch \
  --model general-wdn \
  --scale 2 \
  --font-model general-wdn \
  --font-scale 4 \
  --jpeg-quality 90 \
  --out samples/full

uv run hd-textures pack \
  --from samples/full \
  --pk3 ../../run/codmod/codmod_hd.pk3
```

### Gentle world textures (anti-halo, default)

The plain `general-wdn` result rings around high-contrast edges (dark halos, thickened black outlines, pale
fringes; visible on officer/infantry uniform badges and on text/stone outlines). The 4x network output is then
downsampled to 2x with Lanczos, which adds its own ringing, and the network also darkens edges. `batch` therefore
applies these world-texture settings by default (fonts are never touched):

- `--downsample box` (default) box filter for 4x -> 2x (no ringing); `lanczos`, `bicubic` are the alternatives.
- `--ring-clamp 0.02 --ring-radius 1` (default) limit each output pixel to the local min/max of a bicubic 2x of the
  source (3x3 window, +-0.02) so no overshoot beyond the source's own edges survives; `--no-ring-clamp` turns it off.
- `--blend 0.85` (default) mix 85% AI with 15% bicubic (keeps ~1.2-1.3x the source's high-frequency energy vs ~1.4x
  for pure AI; the blend also fixes the darkening). Use `--blend 0.7` for even less halo, `--blend 1` for pure AI.

The old pure-AI look is `--blend 1 --no-ring-clamp --downsample lanczos`.

### Refresh fonts only (merge into an existing pk3)

When `codmod_hd.pk3` already exists and you only need to replace the 8 font TGAs:

```bash
uv run hd-textures batch \
  --model general-wdn \
  --scale 2 \
  --font-model general-wdn \
  --font-scale 4 \
  --only-fonts \
  --out samples/fonts

uv run hd-textures pack \
  --from samples/fonts \
  --pk3 ../../run/codmod/codmod_hd.pk3 \
  --merge
```

`--merge` replaces/adds those images and keeps every other member of the pk3.

Then launch normally:

```bash
./scripts/run.sh +spdevmap escape1
```

`mod/codmod/codmod.cfg` already sets `r_picmip 0` and `r_picmip2 0` (required or HD is discarded). After replacing the pk3, restart the game or `/vid_restart`.

Expect roughly **~250–300 MiB** pk3 and a few minutes on a mid-range NVIDIA GPU (font-only refresh is seconds).

## Pilot (A/B models before a full run)

```bash
uv run hd-textures pilot \
  --out samples/pilot \
  --scale 2 \
  --models x2plus,general-wdn,animevideov3,ultrasharp
```

Optional model `ani4k` (native 2× Compact, downloaded on first use from
[Sirosky/Upscale-Hub](https://github.com/Sirosky/Upscale-Hub/releases/tag/Ani4K)) — add `ani4k` to `--models`.

The command prints a **device banner** (must say CUDA + GPU name), writes
previews under `samples/pilot/preview/`, and `samples/pilot/report.json` with
timings and compressed sizes. Compare sheets can be built from those previews.

`--scale 4` cascades native-2× models (run twice) or uses native-4× weights as-is.

## Models

| id | Notes |
|---|---|
| `general-wdn` | **World @ 2×** and **fonts @ 4×**. [`realesr-general-wdn-x4v3`](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth) ([release](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0), [repo](https://github.com/xinntao/Real-ESRGAN)) |
| `animevideov3` | Tried for fonts; not preferred |
| `ultrasharp` | Tried for fonts; looked odd in-game |
| `x2plus` | RealESRGAN x2plus (native 2×) |
| `ani4k` | [2x Ani4K Compact](https://github.com/Sirosky/Upscale-Hub/releases/tag/Ani4K) (native 2×), downloaded on first use. Optional |

### Model licenses

Weights are downloaded on first use and are **not** part of this repository. Only `general-wdn` is used for the
pack we ship settings for; the others are optional experiments.

- `general-wdn`, `x2plus`, `animevideov3`: [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) by Xintao Wang et al.,
  BSD 3-Clause license.
- `ultrasharp` ([Kim2091/UltraSharp](https://huggingface.co/Kim2091/UltraSharp)) and `ani4k`
  ([Sirosky/Upscale-Hub](https://github.com/Sirosky/Upscale-Hub)) are third-party community models with their own
  terms (UltraSharp is, to our knowledge, non-commercial). Read them on the model pages before use.

## Inventory

```bash
uv run hd-textures inventory
```

Lists unique SP images from `pak0` + `sp_pak*` (~2400 files).

## Legal

- Redistribute **this tool** freely.
- Do **not** redistribute generated `samples/` or `codmod_hd.pk3`.
- Weights for Real-ESRGAN family are downloaded on first use into `.cache/models/` (gitignored).
