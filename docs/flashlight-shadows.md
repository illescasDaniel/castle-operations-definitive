# Flashlight: per-pixel light on models, shadows

Engine side lives in `iortcw/` (see `iortcw/CODMOD.md`, "rend2 additions").

- **Models lit per pixel** (`R_DlightEntity`, `r_dlightEntities`), additive specular for metal (`r_dlightSpecular`),
  optional albedo lift for near-black materials (`r_dlightAlbedoLift`, default 1 = off; <1 lifts, tested 0.6-0.7 with little effect on dark iron bars).
- **Shadows:** one spot shadow map from the flashlight (`REF_SHADOW_DLIGHT` set in `CG_CodAddFlashlight`), screen-space
  mask, sampled by the dlight shaders. `r_flashlightShadow` 0/1 (2 = show mask inset, debug), `r_flashlightShadowSize`
  (latched, default 1024). Needs `r_depthPrepass 1`. The player's own body/weapon are excluded from the map.
- **Why not `r_dlightMode 2`:** its cube shadows are broken (cubemap bound to a sampler2D, `pvsOrigin` never set);
  one perspective map is also 6x cheaper.
- **Static models (cages, iron gates) were unlit (fixed 2026-10-13):** these are MD3 props drawn from GPU buffers
  (VAO). They had a dlight mask but three rend2 gaps lost the light: the backend ORed the mask after the surface call
  (VAO surfaces draw inside it), `RB_BeginSurface` restarts zeroed `tess.dlightBits`, and `ForwardDlight` used the
  world shader variant, which skips `u_ModelMatrix`, so model-space vertices were lit as if in world space. It was
  not a material problem: the albedo lift and the shadows were red herrings. Exact fixes in `iortcw/CODMOD.md`.
- **Debugging tip:** the issue was found with temporary prints (shader names along the crosshair ray, `tess.dlightBits`
  per draw). Load with `+devmap <map>` (cheats on) and `noclip` out of the `escape1` cell.
