# Pilot listening guide

## Locked (2026-10-11)

| Layer | Choice | Why |
|-------|--------|-----|
| SFX / dialogue | **`sr_only`** | Denoise/enhance dulled intentional VO processing |
| Music | **`sr_linked`** | Same-seed L/R AudioSR — true remaster, no stereo haze |

Full pack: `./remaster.sh` (see [`README.md`](README.md)).

## Re-check pilots (optional)

```bash
cd tools/hd-audio
uv run hd-audio pilot --out samples/pilot --recipes sr_only
uv run hd-audio pilot-music --out samples/pilot-music
```

`samples/` is gitignored — do not redistribute.
