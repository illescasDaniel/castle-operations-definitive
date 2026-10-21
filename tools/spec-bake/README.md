# spec-bake: hand-tagged specular maps (experiment)

Bakes rend2 `<texture>_s.png` maps (rgb = reflectance at normal incidence, alpha = gloss) for a small set of
materials (weapon metal, armor, `textures/metal_misc/*`, a few wood/marble floors) into `run/codmod/codmod_spec.pk3`.
rend2 picks them up automatically while `r_specularMapping 1`. The pk3 is derived from RTCW textures: git-ignored,
never redistribute. Rules live in `RULES` / `MATERIALS` at the top of `spec_bake.py`.
Source priority: `codmod_zfix.pk3` (tools/asset-fixes, run it first) > `codmod_hd.pk3` > game paks.

Built automatically (when stale) by `scripts/setup.sh` / `scripts/install.sh` via `scripts/build-derived-packs.sh [--force]`.

```bash
python3 -I tools/spec-bake/spec_bake.py --list   # what matches
python3 -I tools/spec-bake/spec_bake.py          # write the pk3
```

Findings (escape1 smoke, 2026-10-16): with the engine default `r_deluxeSpecular 0.1` the pack changes almost nothing
(world specular is scaled to 10%). With `r_deluxeSpecular 1` armor and weapon metal read as metal and floors get a faint
sheen. RTCW BSPs have no deluxemaps, so wall/floor highlights have no real light direction.

Try it in game (latched cvars, so pass them on the command line):

```bash
scripts/run.sh +set r_deluxeSpecular 1 +set r_cubeMapping 1
```
