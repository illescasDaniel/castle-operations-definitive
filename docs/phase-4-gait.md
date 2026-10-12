# Phase 4 — Gait / movement presentation

**Prerequisite:** Phase 3 ADS core accepted (per-weapon iron-sight bake may still be deferred).
**Read first:** [architecture.md](architecture.md). This phase is **procedural** first-person
presentation: RTCW viewmodels have no walk/run/sprint anims (IDLE/ATTACK/RELOAD only).

## Goal

Make walk vs jog vs sprint **readable in first person**, like CoD:

| Gait | Feel |
|---|---|
| Walk (`BUTTON_WALKING`) | Calmer gun/camera bob |
| Jog | Combat pace; gun up; can fire |
| Sprint (`COD_SF_SPRINTING`) | Gun lowered; heavier/faster bob + camera weight |

Third-person already picks `ANIM_MT_WALK` vs `ANIM_MT_RUN`. There is no sprint legs move-type;
this phase does **not** invent new skeletal anims.

## Behaviour

### 4.1 Sprint weapon presentation + fire

**Rule (user decision 2026-10-08):** firing while sprinting **ends the sprint and shoots**
the same frame. No fire-block / sprint-out delay before the shot.

Pmove (`PM_CodUpdateSprint`):

- Add `!( buttons & BUTTON_ATTACK )` to `wantSprint`. Attack clears `COD_SF_SPRINTING` before
  `PM_Weapon` runs, so the pressed attack fires normally.
- ADS already cancels sprint (phase 3); keep that priority.

Cgame (visual only):

- While sprinting: procedurally lower/rotate the viewmodel (`cod_sprintGunPitch/Roll/Fwd/Up`).
- On sprint end (release or fire): ease back up over `cod_sprintRaiseTime` (~180 ms).
  **Must not gate firing.**
- Skip the lower while ADS (`CG_CodAdsFrac() > 0`).

### 4.2 Gait-scaled bob

`PM_Footsteps`: for the player when `cod_gaitEnable`, set `bobmove` from gait:

| Gait | Cvar | Default |
|---|---|---|
| Walk | `cod_bobWalkRate` | 0.28 |
| Jog | `cod_bobRunRate` | 0.40 |
| Sprint | `cod_bobSprintRate` | 0.50 |

Cgame weapon + camera bob amplitudes multiply by:

| Gait | Cvar | Default |
|---|---|---|
| Walk | `cod_bobWalkAmp` | 0.65 |
| Jog | `cod_bobRunAmp` | 1.0 |
| Sprint | `cod_bobSprintAmp` | 1.35 |

(CoD4 shipped bob refs in [reference-values.md](reference-values.md); these are starting points.)

### 4.3 Sprint camera weight

While sprinting (lerped with the same visual sprint fraction):

- Scale velocity runpitch/runroll by `cod_sprintRunPitch` / `cod_sprintRunRoll` (defaults 1.75 / 1.5)
- Optional FOV punch: `fov_x *= 1 + (cod_sprintFovScale - 1) * sprintFrac` (default 1.03)

## Cvars

| Cvar | Default | Notes |
|---|---|---|
| `cod_gaitEnable` | 1 | Master for this phase’s presentation (gun lower, bob, camera) |
| `cod_sprintRaiseTime` | 180 | ms, visual gun raise after sprint ends |
| `cod_sprintGunPitch` | 9 | degrees, viewmodel pitch while fully lowered (was 14; raised 2026-10-08 so more gun stays on-screen) |
| `cod_sprintGunRoll` | -8 | degrees |
| `cod_sprintGunFwd` | -1.5 | u along view forward (neg = back toward camera) |
| `cod_sprintGunUp` | -0.5 | u (was -3; less drop so the weapon sits higher in frame) |
| `cod_bobWalkRate` / `Run` / `Sprint` | 0.28 / 0.40 / 0.50 | pmove `bobmove` |
| `cod_bobWalkAmp` / `Run` / `Sprint` | 0.65 / 1.0 / 1.35 | cgame bob multipliers |
| `cod_sprintRunPitch` / `Roll` | 1.75 / 1.5 | × `cg_runpitch` / `cg_runroll` while sprinting |
| `cod_sprintFovScale` | 1.03 | FOV scale at full sprint (1 = off) |

## Files

| Area | Touch |
|---|---|
| Tuning | `bg_cod.h` / `bg_cod.c`, `/cod_menu` section **GAIT** |
| Pmove | `bg_pmove.c` — attack cancels sprint; gait `bobmove` |
| Viewmodel | `cg_weapons.c` — sprint lower + gait bob amp |
| Camera / FOV | `cg_view.c` — gait bob amp, sprint runpitch/roll, FOV |
| Sprint frac | `cg_cod.c` / `cg_local.h` — `CG_CodSprintFrac()` |

## Acceptance

- [ ] Walk: calmer bob than jog
- [ ] Jog: gun up, can fire
- [ ] Sprint: gun lowered; bob/camera heavier than jog
- [ ] Fire while sprinting: sprint ends, shot fires immediately; gun eases up visually
- [ ] Release sprint without firing: gun eases up; next shot normal
- [ ] `cod_enable 0` / `cod_gaitEnable 0`: vanilla pose/bob
- [ ] No new `cg_showmiss` errors

Then **stop** for in-game confirm before Phase 5 (slide).
