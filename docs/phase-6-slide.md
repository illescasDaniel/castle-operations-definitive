# Phase 6 — Tactical Slide

**Prerequisite:** Phase 5d (binds / toggle crouch / flashlight / reload anim) confirmed.
**Read first:** [architecture.md](architecture.md). All slide state must be networked and
time-based (golden rules 2 & 3).

## Behaviour spec

| | |
|---|---|
| **Trigger** | Player is sprinting (`COD_SF_SPRINTING`) **and** presses crouch (`cmd.upmove < 0`) while standing on the ground, moving forward, at horizontal speed ≥ `cod_slideMinSpeed` (260), and the cooldown is over |
| **Start** | Camera drops to crouch height (crouch bbox), velocity keeps its direction and gets `+cod_slideBoost` (60), capped at `cod_slideMaxSpeed` (380) |
| **During** | No friction and no normal acceleration. Speed decays **linearly** from start speed to `cod_slideEndSpeed` (130 = crouch speed) over `cod_slideTime` (1200 ms). Limited steering (`cod_slideSteer`). Can fire, can't ADS (default), can't sprint |
| **End** | Timer runs out, or speed falls to the end speed (e.g. hit a wall) → stand up at crouch-end speed when there is headroom (CoD-style; sticky toggle crouch is cleared). Under a low ceiling, stay crouched until clear |
| **Cancel** | Jump (`cod_slideJumpCancel 1`) → normal jump that keeps momentum. Leaving the ground → slide ends, air move keeps velocity. Entering water or a ladder → ends |
| **Cooldown** | `cod_slideCooldown` (600 ms) after a slide ends |

Expected flat-ground slide distance with defaults: start ≈ 300+60 = 360, end 130, over 1.2 s →
≈ 1.2 × (360+130)/2 ≈ **294 units** (≈ 4 player heights). Use this as a test oracle.

## State (all networked)

| Field | Meaning |
|---|---|
| `pm_flags & PMF_COD_SLIDING` (128) | Sliding now. `#define PMF_COD_SLIDING 128` in `bg_public.h`. **grep first** to confirm 128 is free and add a comment |
| `stats[STAT_COD_SLIDE]` | `> 0`: ms of slide left. `< 0`: cooldown ms left (counts up to 0). `0`: idle |
| `stats[STAT_COD_SLIDE_SPEED]` (new, `stats[11]`) | Start speed (u/s) of the current slide, needed for the linear decay |

Add `STAT_COD_SLIDE_SPEED` to the `STAT_COD_*` block and update
[architecture.md §3](architecture.md#rule-2--new-pmove-state-must-be-networked).

## Implementation — `bg_pmove.c`

### 4.1 Remember pre-duck state
`PM_CheckDuck` runs **before** `PM_GroundTrace` in `PmoveSingle`, and it sets `PMF_DUCKED` as soon as
crouch is held. Add `qboolean codWasDucked;` to `pmoveLocal_t` (`bg_local.h`). Set it right
before `PM_CheckDuck()` is called. (`pml` is memset each call, so set it after the memset.)

### 4.2 `PM_CheckDuck` change
If `pm_flags & PMF_COD_SLIDING`: force `PMF_DUCKED` (crouch bbox and `crouchViewHeight`) even
when crouch is released mid-slide. Otherwise, vanilla.

### 4.3 `static void PM_CodCheckSlideStart( void )`
Call it in `PmoveSingle` **after** the first `PM_GroundTrace()` and **before** the move-type
dispatch. Player only, enabled, not already sliding, `stats[STAT_COD_SLIDE] >= 0`.
```
if ( (stats[STAT_COD_FLAGS] & COD_SF_SPRINTING) && cmd.upmove < 0 && !pml.codWasDucked
     && pml.walking && cmd.forwardmove > 0 && waterlevel < 2 && !pml.ladder
     && hspeed >= bg_cod.slideMinSpeed ) {
	start = min( hspeed + slideBoost, slideMaxSpeed );
	set PMF_COD_SLIDING; stats[SLIDE] = slideTime; stats[SLIDE_SPEED] = start;
	clear COD_SF_SPRINTING;
	velocity.xy = normalize(velocity.xy) * start;
	PM_AddEvent( EV_COD_SLIDE );   // optional, see 4.7
}
```
The sprint flag is from the previous command and is networked, so this is prediction-safe.

### 4.4 `static void PM_CodSlideMove( void )`
In the dispatch, use it instead of `PM_WalkMove()` when `pml.walking && (pm_flags & PMF_COD_SLIDING)`:
1. Jump cancel: if `cod_slideJumpCancel` and `PM_CheckJump()` succeeds → end slide
   (see 4.5) and run `PM_AirMove()`, the same as `PM_WalkMove`'s jump path. Also stand up if
   there is headroom (clear `PMF_DUCKED` after a trace like the one in `PM_CheckDuck`).
2. `stats[SLIDE] -= pml.msec`. `t = max(0, stats[SLIDE]) / slideTime`.
   `speed = slideEndSpeed + ( stats[SLIDE_SPEED] - slideEndSpeed ) * t`.
3. Steering: build `wishdir` from `pml.forward/right` and the cmd as in `PM_WalkMove`. Then
   `dir = normalize( dir + wishdir * slideSteer * pml.frametime * 4 )` (tune the constant so
   steering feels like a gentle carve, not strafing).
4. `velocity.xy = dir * speed`. Clip to the ground plane (`PM_ClipVelocity` with
   `pml.groundTrace.plane.normal`, `OVERCLIP`), then `PM_StepSlideMove( qfalse )`.
5. Optional slope term (`cod_slideSlope`, default 0): add `gravity * slope_down_component * frametime`
   to `stats[SLIDE_SPEED]` going downhill. Leave it off at first.
6. End check: `stats[SLIDE] <= 0` **or** horizontal speed after the move `<= slideEndSpeed + 1`
   (hit a wall) → 4.5.
7. Skip `PM_Friction`/`PM_Accelerate` entirely.

### 4.5 `static void PM_CodEndSlide( void )`
Clear `PMF_COD_SLIDING`, `stats[SLIDE] = -slideCooldown`, `stats[SLIDE_SPEED] = 0`. Velocity is
already ≈ crouch speed, so the next `PM_WalkMove` (crouch clamp `speed × crouchScale` = 130)
carries on without a jump. `PMF_DUCKED` stays set. Next frame `PM_CheckDuck` keeps the crouch
if crouch is held, or stands up if not (and there is room).

Also end the slide when not walking (left the ground) or `waterlevel >= 2` or on a ladder.
Do this check at the top of `PM_CodCheckSlideStart` or in the dispatch.

### 4.6 Cooldown & other systems
- Cooldown tick: in the same per-frame function, `if ( stats[SLIDE] < 0 ) stats[SLIDE] = min( 0, stats[SLIDE] + msec )`.
- `PM_CodUpdateSprint`: no sprint while sliding.
- `BG_CodCanADS`: false while sliding unless `cod_slideAllowADS 1`.
- `PM_UpdateLean`: no lean while sliding.
- `PM_Footsteps`: no footstep events and no bob advance while sliding (treat it like an idle
  crouch for `bobCycle`). Keep the legs anim as crouch (`BG_AnimScriptAnimation` sees `PMF_DUCKED`).
- Stamina: optional `cod_slideStaminaCost` (default 0).
- Prone (phase 5b): `+prone` is ignored while sliding, unless `cod_slideToProne 1` (added in 5b).
- Savegame: if `stats[SLIDE] > 0` without `PMF_COD_SLIDING` (flags aren't saved), set it to 0.

### 4.7 Optional event & sound
Add `EV_COD_SLIDE` to `entity_event_t` just before `EV_MAX_EVENTS` (check that the event count
stays < 256, the 8-bit event field). In `cg_event.c`, play a short scrape. Pick an existing sound
from the paks (list them with `unzip -l pak0.pk3 | grep -i "sound/.*\(slide\|scrape\|gravel\)"`).
No new assets in this phase.

## Camera & viewmodel feel — `cgame`

Read `cg.predictedPlayerState` and compute the eased slide fraction
`s = smoothstep( stats[SLIDE] / slideTime )` (0 when not sliding). Ease the start over ~120 ms
using the time since the slide began (track `cg.codSlideStartTime` from the flag edge).
- View roll: `+ cod_slideRoll` (4°) × s, in `CG_OffsetFirstPersonView`.
- FOV kick: `fov_x *= 1 + cod_slideFovKick (0.05) × s`. Apply it after ADS in `CG_CalcFov`.
- Viewmodel: lower by ~3 u and roll −8° × s in `CG_CalculateWeaponPosition`.
- The camera drop to crouch height comes for free from the existing duck smoothing
  (`cg.duckChange`), which now uses `cod_duckTime` and easing.

## Test plan (also see [testing.md](testing.md))

| # | Scenario | Expected |
|---|---|---|
| 1 | Flat ground, sprint → crouch | Slide ≈ 294 u (HUD shows speed falling linearly 360 → 130 over 1.2 s), then stands |
| 2 | Hold crouch through slide end | Still stands (CoD); under a low ceiling stays crouched until clear |
| 3 | Slide under a low obstacle (crouch-only gap) | Fits through, ends crouched, can't stand until clear |
| 4 | Slide into a wall | Ends early, no jitter, no stuck |
| 5 | Slide off a ledge | Slide ends, momentum carries into the fall |
| 6 | Slide + jump | Jump keeps the forward momentum. Stands if possible |
| 7 | Crouch while jogging (not sprinting) | Normal crouch, no slide |
| 8 | Sprint with empty stamina → crouch | No slide (not sprinting) |
| 9 | Slide spam | Second slide blocked for 600 ms after the end |
| 10 | Fire during slide | Works. ADS blocked (default) |
| 11 | `com_maxfps 60` vs `250` | Same distance ±5% |
| 12 | `cg_showmiss 1` during all of the above | No prediction errors |
| 13 | Save during slide, then load | Loads cleanly, not stuck sliding |
| 14 | AI | No AI ever slides. Patrols unchanged |

## Acceptance criteria (gate)
- [ ] All 14 scenarios pass.
- [ ] `cod_slideEnable 0` disables it completely.
- [ ] Report with the final default values, then **stop**.
