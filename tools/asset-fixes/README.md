# asset-fixes

Private per-texture fixes for broken RTCW art. `fix_assets.py` reads each texture from the owned paks (HD pack
preferred), applies the fix registered in `FIXES` and writes `run/codmod/codmod_zfix.pk3` (sorts after
`codmod_hd.pk3`, so it overrides it). Output is an RTCW derivative: git-ignored, never commit it.

    python3 -I tools/asset-fixes/fix_assets.py [--list] [--preview DIR]

Built automatically (when stale) by `scripts/setup.sh` / `scripts/install.sh` via `scripts/build-derived-packs.sh [--force]`.

Run order: hd-textures -> fix_assets -> spec-bake (spec-bake must read `codmod_zfix.pk3` before `codmod_hd.pk3`).
The fix is written at the resolution of the source it was read from (512 with the HD pack, else 256), so re-run
after regenerating the HD pack.

Fixes:
- `models/mapobjects/knight/knt.tga`: the knight's pauldron/plate triangles map into an empty black diamond
  (u 0.65-0.87, v 0.03-0.26); it is a dump spot for hidden faces (helmet interior, neck hole, limb caps), so it is filled with the helmet-side plate of the same atlas, darkened to dull steel (0.5x the armor median luma, armor-typical alpha) and feathered.
