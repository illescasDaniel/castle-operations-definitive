# Post effects: bloom and colour grade

Both are on by default (`r_bloom 2` = Medium, `r_grade 1`); an existing wolfconfig with a saved `seta r_bloom "0"` / `seta r_grade "0"` keeps the user's old choice (archived cvars; only Reset restores the new defaults). Code:
`RB_PostFx` in `iortcw/SP/code/rend2/tr_postprocess.c`, called from `RB_PostProcess` (`tr_backend.c`) after SMAA and
sun rays. Shaders: `glsl/bloombright_fp.glsl`, `glsl/grade_fp.glsl`.

Menu: GRAPHICS > Bloom (Off/Low/Medium/High = `r_bloom` 0-3, scales `r_bloomIntensity` x0/1/1.6/2.4 (levels retuned 2026-10-17: Low = old Medium, Medium = old High, High = 1.5x old High)) and Color Grade
(`r_grade`), live, no restart. The engine default is off (`tr_init.c`); codmod's on values and the reset value are in `codmod_defaults.cfg`.

Pipeline (runs on the tone-mapped 3D scene, so the HUD/2D is untouched):
1. Bright pass into a half-resolution RGBA16F image (`bloomImage[0]`): 4 bilinear taps, each soft-knee thresholded
   (max channel) before averaging, so small lights neither shimmer nor alias.
2. Five-level mip chain (1/2 .. 1/32) by 2x linear downsamples.
3. Upsample from the smallest level: each level is 3x3-tent filtered onto the next larger one (additive, weight 1.7,
   because small bright areas leave little energy in small mips). Result: a tight glow hugging each light plus a
   wide faint halo, not one big blur. (The first two versions blurred a single 256x256 buffer: it read as a floating
   blob of light, which was the user's complaint.)
4. One grade pass: screen-blend bloom, contrast (pivot 0.35), saturation, warm/cool split tint, vignette
   (scene -> screenScratch -> scene).

| Cvar | Default | Meaning |
|---|---|---|
| `r_bloom` | 2 | 0 off, 1-3 low/medium/high (default medium) |
| `r_bloomIntensity` | 2.5 | glow gain (bright excess x this, mip levels normalised, screen-blended) before the level multiplier |
| `r_bloomThreshold` | 0.6 | brightness (0..1, after tone mapping) where glow starts |
| `r_bloomRadius` | 1.0 | blur width multiplier |
| `r_grade` | 1 | grade on/off |
| `r_gradeBrightness` | 1.25 | gamma lift (1 = none); raises shadows/mids, the game is dark |
| `r_gradeContrast` / `r_gradeSaturation` | 1.06 / 1.10 | |
| `r_gradeTint` | 0.3 | -1 cool highlights .. +1 warm highlights |
| `r_gradeVignette` | 0.1 | edge darkening |

The tuning cvars are not archived and are pinned in `codmod.cfg`; only `r_bloom` and `r_grade` are user settings.
Review 2026-10-17: an A/B of the deterministic bench frame (bloom off vs on, amplified diff) shows glow around torches/lamps and
lit highlights; the first version was nearly invisible (max +16/255 at High) and striped from undersampling.

Bloom works on LDR (after tone mapping), so it cannot glow from values above white.

## Cost (bench demo, 2561x1601, SMAA High, median of 3, same session)

| Config | avg FPS | frame ms |
|---|---|---|
| off | 270 | 3.68 |
| bloom Medium (mip chain) | 247 | 3.98 (+0.30) |
| grade only (earlier, other session) | -22 of 291 | +0.33 |

Lesson from the first version: its blur at half resolution cost 0.74 ms because of per-draw overhead (5 blits per
axis), not pixels; the mip chain needs only 1 bright pass, 4 blits and 4 tent draws.

Note (2026-10-17): the first versions drew every glow upside down (torches lit the floor, floor glints lit the
walls: the "misplaced lights"). `FBO_Blit` flips Y when a source box is paired with a NULL destination box; the
bright pass now blits whole texture to whole texture. `FBO_Blit` also overwrites `u_InvTexRes` (texScale / source
size), so the radius is passed as the texScale. The up chain uses weight 0.8 per level and is normalised by the
weight sum, so large bright areas no longer get ~9x gain.

## Highlight roll-off (2026-10-22)
Bright sky/windows used to clip to flat white (tonemap hard clamp + bloom screen-blend on top). `tonemap_fp.glsl` now
rolls values above `SHOULDER_KNEE` (0.7) off Reinhard-style instead of clamping, and bloom is pinned lower
(`r_bloomThreshold` 0.8, `r_bloomIntensity` 1.8, was 0.6 / 2.5) so it no longer washes the sky out. Torch/lamp glow is
a little tighter. Tune in `codmod.cfg`; revert the shoulder by making the knee 1.0.
