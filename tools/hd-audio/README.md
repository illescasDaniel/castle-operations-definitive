# hd-audio — local AI remaster for RTCW SP

Remasters Return to Castle Wolfenstein **single-player** audio from your owned
Steam `.pk3` files (AudioSR bandwidth extend to 48 kHz; music uses linked stereo
SR). The **script is shareable**; the **remastered WAVs / pk3 are not**.

Do **not** commit or redistribute `codmod_hd_audio.pk3` or anything under
`samples/`. Those are derivatives of proprietary id/Activision assets. Everyone
re-runs this tool against their own install.

## Requirements

- Python **3.11** (pinned; `audiosr==0.0.7`) and [uv](https://github.com/astral-sh/uv)
- NVIDIA GPU + CUDA (tuned for **8 GB**: CPU-load checkpoint, VAE/UNet staging,
  GPU diffuse + CPU decode/vocoder, 5 s chunks)
- Steam RTCW `Main/` with `pak0.pk3`, `sp_pak1.pk3` (and optional `sp_pak2–4`)
- Repo `./scripts/setup.sh` once so `run/codmod/` exists
- Close other GPU-heavy apps before a full batch (~6–7 GB free VRAM helps)

Default data path (override with `--data` or `RTCW_DATA`):

`~/.local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main`

## Locked recipe (2026-10-11)

| Layer | Setting | Notes |
|-------|---------|--------|
| SFX / dialogue | **`sr_only`** | AudioSR only — denoise/enhance dulled intentional VO FX |
| Music | **`sr_linked`** | AudioSR L/R with **same seed**, guidance ≤ 2.0 |

~1360 unique `sound/**/*.wav` files (later pak wins). Full batch is **hours** on
an 8 GB laptop GPU; use `--resume` (default in `remaster.sh`).

## Generate the current audio pack (recommended)

From the repo root (after `scripts/setup.sh`):

```bash
cd tools/hd-audio
chmod +x remaster.sh   # once
./remaster.sh
```

That will:

1. `uv sync --python 3.11`
2. `hd-audio batch --recipe sr_only --music-mode sr_linked --resume --out samples/full`
3. `hd-audio pack` → `../../run/codmod/codmod_hd_audio.pk3`

Interrupted overnight? Re-run the same command — `--resume` skips finished WAVs.

Pack only (after a completed batch):

```bash
./remaster.sh --pack-only
```

Fresh reprocess (ignore existing WAVs):

```bash
./remaster.sh --fresh
```

Then launch:

```bash
./scripts/run.sh +spdevmap escape1
```

The engine loads every `*.pk3` under `fs_game` `codmod`. Paths inside
`codmod_hd_audio.pk3` mirror vanilla (`sound/...`), so they override Steam paks.
`s_useOpenAL` defaults to `1` (native rates); `codmod.cfg` pins it on. Restart
the game after replacing the pk3 (audio is latch-sensitive).

Expect a **large** pk3 (hundreds of MiB–~1+ GiB as 48 kHz PCM). Do not redistribute it.

## Manual commands (same as the script)

```bash
cd tools/hd-audio
uv sync --python 3.11

uv run hd-audio batch \
  --recipe sr_only \
  --music-mode sr_linked \
  --resume \
  --out samples/full

uv run hd-audio pack \
  --from samples/full \
  --pk3 ../../run/codmod/codmod_hd_audio.pk3
```

Optional filters: `--category music|sfx|speech`, `--limit N` (debug).

## Pilot / A/B (optional)

SFX/VO recipes and music modes were already locked; keep these for re-checks:

```bash
uv run hd-audio pilot --out samples/pilot --recipes sr_only
uv run hd-audio pilot-music --out samples/pilot-music --modes resample,sr_mid,sr_linked
```

See [`LISTEN.md`](LISTEN.md).

## Inventory

```bash
uv run hd-audio inventory
```

## Legal

- Redistribute **this tool** freely.
- Do **not** redistribute generated `samples/` or `codmod_hd_audio.pk3`.
- [AudioSR](https://github.com/haoheliu/versatile_audio_super_resolution) (Haohe Liu et al.) is pulled on first
  use (`audiosr==0.0.7`, pip package licensed MIT). The model weights download from the project's own page: review
  their terms before sharing any output. Credit that project if you publish results.
