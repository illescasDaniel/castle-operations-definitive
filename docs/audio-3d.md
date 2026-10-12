# 3D audio (HRTF)

Positional sound already ran through OpenAL Soft (`iortcw/SP/code/client/snd_openal.c`); every entity sound has a
3D position and the listener follows the camera. HRTF only changes how that is rendered to two ears, so no
gameplay/cgame code is involved.

## Cvars (engine)

| Cvar | Default | Meaning |
|---|---|---|
| `s_alHRTF` | `1` | `0` off, non-zero on (forces binaural stereo). OpenAL Soft's auto mode never triggered here, so it is not offered |
| `s_alHRTFProfile` | `""` | HRTF profile name (see `s_info`, or `s_alAvailableHRTFs`); empty = default |
| `s_alAvailableHRTFs` | ROM | List of profiles reported by OpenAL Soft |

Changes apply live (`alcResetDeviceSOFT` from `S_AL_Update`), no `snd_restart`. `s_info` prints HRTF status.
Menu row: Setup → Sound → "3D Audio (HRTF)" On/Off (main and in-game). Not pinned in `codmod.cfg` so the menu choice sticks.

## Libraries considered

- **OpenAL Soft** (LGPL-2.1, loaded at runtime via dlopen): used. Built-in HRTF, custom `.mhr`/SOFA profiles, EFX.
- **Steam Audio** (Apache-2.0): not used; would replace the mixer. Only worthwhile for geometry-based occlusion/reflections.
- **libspatialaudio** (LGPL-2.1): not used; OpenAL Soft already does the binaural rendering.

Engine is GPL regardless; the mod files/tools are unaffected.

## Notes

- HRTF applies to mono sources only. SFX are mono (HD remaster keeps them mono); music is stereo and unaffected.
- Custom HRTF: drop `.mhr` files in `~/.local/share/openal/hrtf/` and set `s_alHRTFProfile`.
- Possible next steps: EFX reverb per area, low-pass occlusion via a trace.
