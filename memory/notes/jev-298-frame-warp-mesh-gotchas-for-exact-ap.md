---
name: jev-298-frame-warp-mesh-gotchas-for-exact-ap
description: "2026-10-28 frame warp mesh gotchas  for exact AP screenshot comparisons set r_sunShadowCascadeUpdate 0 (mesh t"
type: incident
date: 2026-10-28
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 298, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

2026-10-28 frame warp mesh gotchas: for exact AP screenshot comparisons set r_sunShadowCascadeUpdate 0 (mesh timing shifts the cascade update phase, otherwise ~88% of pixels differ). FBO_BlitFromTexture with NULL corners samples upside down; use FBO_Blit. R_WarpMatrix is new->old, the mesh camera rotation is its transpose. Warp dt must be measured in present time and read before the replayed 2D tail (its swap clears ap.inflight). The depth grid must be snapshotted at capture because renderDepthImage is overwritten by the next frame. Mesh cost is raster-bound by triangle count (~72k tris at level 2), not shader-bound.

