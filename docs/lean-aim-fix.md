# Lean + aim: shots land above the crosshair (fix plan)

Status: steps 1-3 implemented 2026-10-15 (engine `3e63880a`), pending the user's in-game check. Executor: follow the steps in order, then stop for the
user's in-game check (phase gating, `docs/testing.md`).

## Symptom

While leaning (and aiming down sights), bullets hit **above** the crosshair. Without lean, shots
land on the crosshair.

## Root cause

The camera and the server compute the lean offset with different "right" vectors.

- **Camera**, `iortcw/SP/code/cgame/cg_view.c` ~L764-792 (`CG_OffsetFirstPersonView`): first adds the
  lean roll to `cg.refdefViewAngles[ROLL]` (`leanf * cod_leanRollScale`, about 19° at full lean),
  *then* calls `AngleVectors( cg.refdefViewAngles, ... right ... )` and moves the eye by
  `leanf * right`. With roll, `right` is tilted, so `right[2] = -sin(roll) * cos(pitch)`, which is
  negative for both lean directions (roll and leanf share the sign). The camera therefore **drops**
  by `|leanf| * sin(roll)`, and its sideways offset shrinks to `leanf * cos(roll)`.
- **Server**, `iortcw/SP/code/game/g_weapon.c` `AddLean` ~L1516: moves the shot origin by
  `leanf * right` with `right` from `ps->viewangles`, which has **no lean roll**. The bullet trace
  start `muzzleTrace` comes from `CalcMuzzlePointForActivate` (eye + `AddLean`, ~L1655), so it stays
  at full eye height.

Numbers with the defaults (`cod_leanMax 32`, `cod_leanRollScale 0.6`, roll 19.2°): the shot starts
`32 * sin(19.2°)` ≈ **10.5 units above** the camera and about 1.8 units further out sideways. The
shot ray is parallel to the view ray, so every impact sits ~10.5 u above the aim point at any range
(very visible close up). Vanilla RTCW had the same mismatch (roll `leanf/2`), hidden because it
did not allow firing while leaning; `cod_leanAllowFire 1` exposed it.

Secondary mismatch: `cod_leanEase 1` smoothsteps the *displayed* leanf in cgame only, so during the
lean-in/out transition the server shot origin uses the raw `ps->leanf` and is sideways off the
camera. At full lean both agree.

## Fix: one shared lean-offset function used by camera and server

Keep the current look (the head dips and rolls when peeking) and make the server fire from exactly
where the camera is.

### Step 1: `BG_CodLeanOffset` in bg_cod (shared by qagame and cgame)

`iortcw/SP/code/game/bg_cod.h`, near the other `BG_Cod*` prototypes:

```c
// codmod: eye offset of a lean, shared by the camera (cg_view.c) and the shot origin (g_weapon.c
// AddLean) so bullets leave from where the player sees. Returns the lean roll in degrees.
float BG_CodLeanOffset( const playerState_t *ps, vec3_t offset );
```

`iortcw/SP/code/game/bg_cod.c` implementation, moving the math out of `cg_view.c` unchanged:

1. `VectorClear( offset )`; if `ps->leanf == 0` return 0.
2. If `bg_cod.enable && bg_cod.leanEnable`: `leanf = ps->leanf`; if `bg_cod.leanEase`, apply the same
   smoothstep on `|leanf| / leanMax` as cg_view.c does today (use `BG_CodSmoothstep`, guard
   `leanMax <= 0` with 1.0f as now); `roll = leanf * bg_cod.leanRollScale`.
   Else (vanilla): `leanf = ps->leanf`, `roll = leanf / 2.0f`.
3. `angles = { ps->viewangles[PITCH], ps->viewangles[YAW], roll }` (use only the lean roll, not
   `ps->viewangles[ROLL]`, so cosmetic camera roll from bob/kick never moves the shot).
4. `AngleVectors( angles, NULL, right, NULL ); VectorScale( right, leanf, offset );` return `roll`.

Deterministic from `playerState_t` + `bg_cod` only, so qagame and cgame get identical results.
Check that `bg_cod.c` is linked into both qagame and cgame (it is, see the `extern codTuning_t
bg_cod` comment in bg_cod.h) and that `q_shared.h`'s `AngleVectors` is available there.

### Step 2: camera uses it (`cgame/cg_view.c` ~L764-792)

Replace both branches of the lean block with:

```c
if ( cg.predictedPlayerState.leanf != 0 ) {
	vec3_t leanOfs;

	// codmod: shared with the server's shot origin (BG_CodLeanOffset), so the bullet leaves
	// from the eye the player sees through
	cg.refdefViewAngles[ROLL] += BG_CodLeanOffset( &cg.predictedPlayerState, leanOfs );
	VectorAdd( cg.refdef.vieworg, leanOfs, cg.refdef.vieworg );
}
```

Behaviour change to accept: the offset is now computed from the predicted view angles plus lean
roll only, instead of `cg.refdefViewAngles` (which at that point may already hold small bob/kick
roll). Visually identical within a fraction of a unit.

### Step 3: server uses it (`game/g_weapon.c` `AddLean` ~L1516)

```c
void AddLean( gentity_t *ent, vec3_t point ) {
	if ( ent->client && ent->client->ps.leanf ) {
		vec3_t leanOfs;

		// codmod: same offset as the camera (BG_CodLeanOffset), including its lean roll dip,
		// so shots land on the crosshair while leaning
		BG_CodLeanOffset( &ent->client->ps, leanOfs );
		VectorAdd( point, leanOfs, point );
	}
}
```

This fixes the bullet trace (`muzzleTrace`), the effect origin (`CalcMuzzlePoint`) and the
use/activate trace in one place. AI never lean (`PM_UpdateLean` returns early on `ps->aiChar`), so
AI fire is unchanged. Update the stale "(SA) actually, this is sort of moot" comment at ~L1603.

### Step 4 (optional, only if the user still sees sights off-center in ADS)

`cgame/cg_weapons.c` ~L1788-1840 (`CG_CalculateWeaponPosition`) shifts and counter-rolls the
viewmodel while leaning (`origin += angles[ROLL] * right`, `origin -= leanf/4 * right`, roll by
`leanf * rollScale / leanscale`). This is cosmetic (bullets go down screen center) but in ADS it can
push the sights off the crosshair. If the user reports that after steps 1-3, fade those three lean
terms by `1 - BG_CodSmoothstep( CG_CodAdsFrac() )` so the sights stay centred in ADS. Do not do this
step unless the user asks; it changes the hip-fire look too if done wrong.

## Build and verify

1. `scripts/build.sh --game-only`; no new warnings in `bg_cod|cg_view|g_weapon` (filter in
   `docs/testing.md`, "Every change").
2. User in-game check (do not script-launch to verify, see `docs/testing.md` safety rules; quit
   cleanly, never kill the game):
   - Stand ~2 m from a flat wall, full lean left, ADS, fire single shots at a small mark: the
     decal must sit on the crosshair / sight dot. Repeat leaning right, then at ~20 m, then while
     looking up/down ~45°.
   - Fire during the lean-in transition (tap lean + fire): impacts stay on the crosshair.
   - No-lean shots unchanged; `cod_leanEnable 0` still works (vanilla path).
   - Camera lean looks the same as before (same dip and roll).
3. Regression list in `docs/testing.md` (lean, ADS, slide, prone rows).

## Commit and bookkeeping

- Code commit in `iortcw/` (branch `main`): "codmod: shots fire from the leaned camera eye
  (BG_CodLeanOffset)".
- Outer repo: update `docs/phase-2-movement.md` section 2.3 (item 2 says g_weapon.c "already
  offsets the muzzle by leanf"; note the shared function and the roll-dip cause), mark this plan
  done, update `memory/progress.md` and `memory/activeContext.md`.
- jevmem `memory_write`: bug cause (camera lean offset used a roll-tilted right vector, server did
  not, so shots fired ~10 u above the crosshair while leaning) and the fix.

## Rejected alternative

Compute the camera offset from the un-rolled right vector (one-line cgame change). It also aligns
camera and shot, but removes the head dip when peeking, which changes the feel the user already
approved. Use it only if the user prefers that look.
