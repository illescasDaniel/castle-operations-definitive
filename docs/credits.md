# Third-party credits

## SMAA (Enhanced Subpixel Morphological Antialiasing)

Used for the `r_smaa` post-process anti-aliasing in the rend2 renderer (`iortcw/SP/code/rend2/`).

- Authors: Jorge Jimenez, Jose I. Echevarria, Belen Masia, Fernando Navarro, Diego Gutierrez
- Project: <http://www.iryoku.com/smaa/> — source: <https://github.com/iryoku/smaa>
- License: MIT (full text kept in each vendored file's header)
- Vendored files:
  - `glsl/smaa_lib.glsl` — from `SMAA.hlsl` (line endings and two non-ASCII comment bytes normalized)
  - `smaa_areatex.h` — from `AreaTex.h` (precomputed area texture)
  - `smaa_searchtex.h` — from `SearchTex.h` (precomputed search texture)
- Our own thin wrappers: `glsl/smaa_{edge,weights,blend}_{vp,fp}.glsl`, and the passes in `tr_postprocess.c`.

Paper: J. Jimenez et al., "SMAA: Enhanced Subpixel Morphological Antialiasing", Computer Graphics Forum 31(2), 2012.

## ioRTCW and the RTCW source

The engine and game code are derived from [ioRTCW](https://github.com/iortcw/iortcw) via our fork
[illescasDaniel/iortcw](https://github.com/illescasDaniel/iortcw) (GPLv3 with additional terms) and
the Return to Castle Wolfenstein source released by id Software. See `LICENSE`.

## Enemy Territory: Legacy

The prone stance (`PM_CheckProne` logic, prone bounding boxes, view limits) is ported from the GPLv3 code of
[ET: Legacy](https://github.com/etlegacy/etlegacy) / id Software's Wolfenstein: Enemy Territory source.

## OpenAL Soft

3D audio uses OpenAL Soft's HRTF (`ALC_SOFT_HRTF`), loaded at runtime from your system (LGPL-2.1). No OpenAL code is vendored.

## Optional AI tools (generated packs are not distributed)

Nothing below is bundled: the tools download the models on your machine on first use.

- `tools/hd-textures`: [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) (Xintao Wang et al., BSD 3-Clause). The
  `general-wdn` model (`realesr-general-wdn-x4v3`) is the one used for the HD texture pack. Also selectable:
  `x2plus`, `animevideov3` (same project), [4x-UltraSharp](https://huggingface.co/Kim2091/UltraSharp) by Kim2091 and
  [2x Ani4K Compact](https://github.com/Sirosky/Upscale-Hub/releases/tag/Ani4K) by Sirosky. These two have their
  own terms; check them before using or sharing output.
- `tools/hd-audio`: [AudioSR](https://github.com/haoheliu/versatile_audio_super_resolution) (Haohe Liu et al.; the
  `audiosr` Python package is MIT licensed, the weights follow the project's own terms).
- `tools/hd-video`: [2xLiveActionV1_SPAN](https://openmodeldb.info/models/2x-LiveActionV1-SPAN) by jcj83429
  (CC-BY-NC-SA-4.0: non-commercial, share-alike; output stays private like the other HD packs), loaded with
  [spandrel](https://github.com/chaiNNer-org/spandrel) (MIT) and run with FFmpeg's `nlmeans` denoiser. The weights
  are downloaded on the user's machine, never bundled. Other models tried (not shipped): 2xNomosUni compact
  multijpg, 4x-ClearReality, 4x-UltraSharpV2 (Kim2091).

Review each model's license before using or sharing its output.

## Original assets

- `mod/codmod/ui/glyphs/*.tga` (controller prompts in `codmod_pad.pk3`): original Xbox-like and PlayStation-like art
  made for this project, not taken from any console maker's assets.
- `mod/codmod/sound/codmod/hitmarker*.wav` (in `codmod_fx.pk3`): short synthesized tones generated with Claude (Anthropic)
  for this project; no third-party samples.
- `mod/codmod/demos/codmod_bench.dm_50`: benchmark demo recorded by the author, contains no third-party data
  beyond the RTCW map it replays (which you load from your own copy).
