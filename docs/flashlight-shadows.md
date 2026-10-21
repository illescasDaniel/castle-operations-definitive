# Flashlight: per-pixel light on models, shadows

Engine side lives in `iortcw/` (see `iortcw/CODMOD.md`, "rend2 additions").

- **Models lit per pixel** (`R_DlightEntity`, `r_dlightEntities`), additive specular for metal (`r_dlightSpecular`),
  optional albedo lift for near-black materials (`r_dlightAlbedoLift`, default 1 = off; <1 lifts, tested 0.6-0.7 with little effect on dark iron bars).
- **Shadows:** one spot shadow map from the flashlight (`REF_SHADOW_DLIGHT` set in `CG_CodAddFlashlight`), screen-space
  mask, sampled by the dlight shaders. `r_flashlightShadow` 0/1 (2 = show mask inset, debug), `r_flashlightShadowSize`
  (latched, engine default 1024; codmod default 2048 via `codmod_gfxdefaults.cfg`, row "Flashlight Shadow Size" in GRAPHICS > ADVANCED and the engine Effects tab). Needs `r_depthPrepass 1`. The player's own body/weapon are excluded from the map.
- **Why not `r_dlightMode 2`:** its cube shadows are broken (cubemap bound to a sampler2D, `pvsOrigin` never set);
  one perspective map is also 6x cheaper.
- **Static models (cages, iron gates) were unlit (fixed 2026-10-13):** these are MD3 props drawn from GPU buffers
  (VAO). They had a dlight mask but three rend2 gaps lost the light: the backend ORed the mask after the surface call
  (VAO surfaces draw inside it), `RB_BeginSurface` restarts zeroed `tess.dlightBits`, and `ForwardDlight` used the
  world shader variant, which skips `u_ModelMatrix`, so model-space vertices were lit as if in world space. It was
  not a material problem: the albedo lift and the shadows were red herrings. Exact fixes in `iortcw/CODMOD.md`.
- **Props/doors/metal dark again (fixed 2026-10-17):** after specular went on by default, auto-found `_s` maps give
  stages `specularScale` 1. `ForwardDlight` bound that map but set `u_EnableTextures.z` = 0, so the shader read
  specular as white x 1 and `diffuse *= 1 - specular` zeroed the albedo: anything with a `_s` map (wood, metal, chains)
  got no flashlight light, plain walls did (`tr_shade.c`, `enableTextures` in `ForwardDlight`). Second, older defect:
  brush models (`func_door` etc.) never received dlights because `R_DlightSurface` compared world-space light positions
  with model-space surface bounds (`tr_world.c`, `r_dlightModelSpace`). Metal bands now flare with `r_deluxeSpecular 3`.
  Found by shader debug output (flat colour per factor) after ruling out culling, depth-EQUAL and the shadow mask.
- **Debugging tip:** the issue was found with temporary prints (shader names along the crosshair ray, `tess.dlightBits`
  per draw). Load with `+devmap <map>` (cheats on) and `noclip` out of the `escape1` cell.

## One-time key tip

After the player has had control in a level for 4 s, a center print "Toggle Flashlight with <key>" (key from the
`toggleflashlight` bind) is shown once per install (`CG_CodUpdateTips`, cg_cod.c). State: archived cvar
`cod_tipFlashlightShown` (default 0, saved in wolfconfig.cfg; not in the mod cfgs). Toggling the flashlight first also
marks it shown; an unbound key leaves it armed. `cod_tipFlashlightShown 0` in the console re-arms it. The text is
translated as a template (see docs/languages.md).
