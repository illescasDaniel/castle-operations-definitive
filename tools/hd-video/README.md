# hd-video — local AI remaster for RTCW SP videos

Remasters the SP cutscene (`wolfintro`) and menu loops (`menu`, `menu2`) and writes MJPEG/AVI files, which the
engine prefers over the original RoQ (`video/<name>.avi`; falls back to RoQ if missing or not power-of-two sized).
Output is derived from proprietary assets: never commit or redistribute `samples/` or `codmod_hd_video.pk3`.
MP videos are out of scope for now (`--only` takes any basename/glob if that changes).

## Credits

Upscaling model: **[2xLiveActionV1_SPAN](https://openmodeldb.info/models/2x-LiveActionV1-SPAN) by jcj83429**
([weights](https://huggingface.co/poor7/Other/blob/02606599eb74781065604c22921f08bef8745b17/2xLiveActionV1_SPAN_490000.pth)),
CC-BY-NC-SA-4.0 (non-commercial, share-alike). The weights are downloaded on your machine on first use and are not
bundled. Models run through [spandrel](https://github.com/chaiNNer-org/spandrel); denoise/decode via FFmpeg.
See `docs/credits.md`.

## Recipe (what we ship)

`nlm1+span`: RoQ decode → ffmpeg `nlmeans=s=1:p=5:r=9` (removes the VQ block artifacts and speckle) →
SPAN 2x (512x256 → 1024x512, 256x256 → 512x512) → dynamic luma film grain (sigma 3, fresh each frame, applied
after upscaling because the denoise removes the original grain) → MJPEG `-q:v 3` + PCM s16le audio (copied from the
RoQ). Result: ~116 MB for the intro, ~130 MB pk3 in total.

Why: SPAN alone keeps the original blockiness; stronger nlmeans (>= 2) turns the picture plasticky; 4x (SPAN twice)
looked odd; UltraSharpV2 was slow and not better. Native-4x models are downscaled to the output scale.

## Reproduce

Needs an NVIDIA GPU (8 GB is enough), ffmpeg, [uv](https://github.com/astral-sh/uv) and the RTCW data
(`RTCW_DATA` or `--data`, the Steam `Main/` dir with pak0 and sp_pak1-4).

```bash
cd tools/hd-video
uv sync --python 3.11
uv run hd-video batch --variant nlm1+span --grain 3   # ~3 min on an RTX 4070 Laptop -> samples/full/nlm1+span/video/*.avi
uv run hd-video pack --variant nlm1+span              # -> ../../run/codmod/codmod_hd_video.pk3
```

The model downloads into `.cache/models` (or copy `2xLiveActionV1_SPAN_490000.pth` into `~/Models` first).
Delete the pk3 to revert to the original videos. Then play the intro with `./scripts/run.sh +cinematic wolfintro.RoQ 3`.

## Other commands

```bash
uv run hd-video pilot --variant nlm1+span --ss 30 --seconds 8      # short clip + stills + size per second
uv run hd-video compare --only wolfintro --ss 30 --seconds 3 \
    --variants span nlm1+span nlm2+span --crop 100,10,200,120       # labelled side-by-side grid in samples/compare/
```

`--variant` names are `[nlm<strength>+]<model>` (see `VARIANTS` in `src/hd_video/cli.py`; models: span, nomos,
clearreality, ultrasharpv2; `span2` chains SPAN twice for 4x). `--grain` (0 = off) and `--quality` apply to
batch/pilot/compare; `--scale 4` forces 4x output.

## Engine side

`iortcw/SP/code/client/cl_cin_avi.c` (MJPEG/AVI reader using the in-tree libjpeg, PCM audio via `S_RawSamples`) and
`cl_cin.c` (`.avi` preferred over `.roq`; letterbox drawn at a fixed 640:270 box fitted to the window so the aspect
is correct on any monitor). Design reasons: `memory/decisions.md` (2026-10-13).
