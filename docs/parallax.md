# Parallax mapping

Relief parallax (with self-shadowing) on walls and floors, driven by AI-generated height maps. rend2 samples a
`<texture>_nh.png` (rgb = tangent-space normal, alpha = height) and marches the view ray through the height field in
`lightall_fp.glsl`. No `gl_FragDepth` is written, so the depth prepass, shadows and SSAO see the flat surface.

## Settings

GRAPHICS > ADVANCED > **Normal Maps** (Off / On) and **Parallax Mapping** (Off / On / On + Self-Shadows); engine layer
too (EFFECTS tab), usable by plain RTCW. Both are latched: press Apply (vid_restart). The group logic is in
`Item_Multi_HandleKey` / `Item_Multi_CvarValue` (`ui_shared.c`). The Parallax row's list values are UI levels (0/2/3),
derived from two cvars for display:

| Parallax level | `r_parallaxMapping` | `r_parallaxMapShadows` | `r_normalMapping` |
|---|---|---|---|
| Off | 0 | 0 | unchanged |
| On | 2 | 0 | set to 1 |
| On + Self-Shadows | 2 | 1 | set to 1 |

Normal Maps Off sets `r_parallaxMapping` 0 and `r_parallaxMapShadows` 0 (parallax needs the `_nh` normals).

Off disables all parallax paths. Engine code defaults are vanilla (0); the mod's first-launch/Reset values are `seta` in
`mod/codmod/codmod_gfxdefaults.cfg` (On). Internal pins in `mod/codmod/codmod.cfg`: `r_parallaxMapOffset 0`,
`r_baseParallax 0.02`, `r_parallaxFloorScale 0.5` (all CVAR_LATCH except floor scale). Engine defaults kept:
`r_parallaxMaxSteps 48`, `r_parallaxFadeDist 1200`, `r_parallaxCavity 0.5` (live, not latched).

## Height pack

`run/codmod/codmod_height.pk3`, built by `tools/height-bake` (DeepBump normals, FFT height integration, plateau
normalisation so surfaces only recess; see its README). Derived from RTCW textures: git-ignored, never redistribute.

```bash
cd tools/height-bake && python3 -m venv .venv && .venv/bin/pip install numpy pillow onnxruntime   # once, plus the model (README)
tools/height-bake/.venv/bin/python -I tools/height-bake/height_bake.py --map escape1 --preview
```

Without the pack, On has no visible effect (rend2 finds no `_nh` file).

## Known limits

- Only textures baked into the pack get depth; so far escape1 (36 wall/floor textures). Other maps need baking.
- Dark or low-contrast textures are confidence-gated to flat; AI heights can still be noisy on fine detail.
- Alpha-tested, blended, animated, tcgen/tcmod, sky, water and deformVertexes shaders are skipped.
- Silhouettes stay flat (no depth write); strong effect at grazing angles fades with `r_parallaxFadeDist`.
- Cost: up to 48 steps per pixel plus shadow march; quality over performance for now.

## Testing

Build menus and game (`scripts/build-menus.sh --export`, `scripts/build.sh --game-only --install`), start escape1,
set the row On, Apply, look at stone walls at grazing angles; compare Off. Check the row survives a restart (saved in
`wolfconfig.cfg`) and that "Restore recommended defaults" turns it On.
