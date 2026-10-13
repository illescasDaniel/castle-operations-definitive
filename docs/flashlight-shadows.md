# Flashlight: per-pixel light on models, shadows

Engine side lives in `iortcw/` (see `iortcw/CODMOD.md`, "rend2 additions").

- **Models lit per pixel** (`R_DlightEntity`, `r_dlightEntities`), additive specular for metal (`r_dlightSpecular`),
  albedo lift so near-black materials still catch light (`r_dlightAlbedoLift`, default 0.6, 1/0 = off).
- **Shadows:** one spot shadow map from the flashlight (`REF_SHADOW_DLIGHT` set in `CG_CodAddFlashlight`), screen-space
  mask, sampled by the dlight shaders. `r_flashlightShadow` 0/1 (2 = show mask inset, debug), `r_flashlightShadowSize`
  (latched, default 1024). Needs `r_depthPrepass 1`. The player's own body/weapon are excluded from the map.
- **Why not `r_dlightMode 2`:** its cube shadows are broken (cubemap bound to a sampler2D, `pvsOrigin` never set);
  one perspective map is also 6x cheaper.
- **Known open item:** the first iron-bar gate in `escape1` (alpha-tested fence, `textures/alpha/fence_m01b`) still
  looks unlit in places.
