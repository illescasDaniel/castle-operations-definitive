# Phase 5 — Movement weight + fire responsiveness

**Prerequisite:** Phase 4 (gait) confirmed.
**Read first:** [architecture.md](architecture.md) (player-only gates), [reference-values.md](reference-values.md).
Promotes E6 / E7 / E17 and pistol tap-fire from [phase-7-extras.md](phase-7-extras.md).

## Goal

Make actions feel more connected to input:

1. **Pistols / semi-auto** — fire nearly as fast as you can click (RTCW SP locks Luger/Colt to 400 ms `nextShotTime`; MP already has tap-fire early-clear that SP disables).
2. **Jump / gravity** — slightly lower jump (CoD4 ≈ 250 vs RTCW 270); player gravity tunable.
3. **Ground inertia** — player-only accel/friction so start/stop has more weight than Quake defaults.
4. **Landing slowdown (E6)** — brief move penalty after a hard-ish land.

AI must keep vanilla fire intervals and physics (same `ammoTable` / `pm_*` globals — override only in player branches).

## Behaviour

### 5.1 Pistol tap-fire + min interval

In `PM_Weapon` (`bg_pmove.c`), for the player when `cod_weaponEnable`:

| Cvar | Default | Role |
|---|---|---|
| `cod_weaponEnable` | 1 | Master for fire-feel |
| `cod_pistolTapFire` | 1 | Re-enable SP `releasedFire` early-clear for Luger / Colt / Silencer |
| `cod_pistolTapThreshold` | 150 | Clear remaining `weaponTime` when ≤ this after release (MP parity) |
| `cod_pistolNextShot` | 200 | Min ms between pistol shots (replaces ammoTable 400 when > 0; was 120, tuned less spammy) |
| `cod_pistolFireDelay` | 0 | Override `fireDelayTime` for those pistols (0 = snappy first shot) |
| `cod_autoFireScale` | 1.0 | Scale `nextShotTime` for MP40/Thompson/Sten/FG42 (1 = unchanged) |

Hold-to-fire still cannot exceed `cod_pistolNextShot`. Full-auto unchanged at scale 1.

### 5.2 Jump + gravity (E7)

| Cvar | Default | Role |
|---|---|---|
| `cod_jumpVelocity` | 250 | `PM_CheckJump` for player (was `JUMP_VELOCITY` 270) |
| `cod_gravity` | 800 | Player `ps.gravity` in `ClientThink_real` (same as vanilla; exposed for tune) |

### 5.3 Ground inertia (E17)

Do **not** mutate file-scope `pm_accelerate` / `pm_friction` (AI shares the process). Use locals in `PM_Friction` / `PM_WalkMove`:

| Cvar | Default | Vanilla |
|---|---|---|
| `cod_accelerate` | 8 | 10 |
| `cod_friction` | 8 | 6 |
| `cod_stopspeed` | 100 | 100 |

Gated on `cod_enable && cod_moveEnable` (same as speeds).

### 5.4 Landing slowdown (E6)

| Cvar | Default | Role |
|---|---|---|
| `cod_landSlowEnable` | 1 | On after any non-trivial land (`PM_CrashLand` delta ≥ 1) |
| `cod_landSlowTime` | 350 | ms of slowdown |
| `cod_landSlowScale` | 0.55 | × wishspeed while active |

State: `stats[STAT_COD_LAND]` (>0 = ms left). Tick in `PmoveSingle`. Networked via existing `stats[]`.

## Files

| Area | Touch |
|---|---|
| Tuning | `bg_cod.h` / `bg_cod.c`, `/cod_menu` **FEEL** + **WEAPON** |
| Fire | `bg_pmove.c` `PM_Weapon` |
| Jump | `bg_pmove.c` `PM_CheckJump` |
| Gravity | `g_active.c` `ClientThink_real` |
| Accel/friction | `bg_pmove.c` `PM_Friction`, `PM_WalkMove` |
| Land | `bg_pmove.c` `PM_CrashLand` + tick + wishspeed scale |
| Stats | `bg_public.h` `STAT_COD_LAND` |

## Acceptance

- [x] Spam-click Luger/Colt: ROF tracks clicks down to `cod_pistolNextShot` (200 ms); `cod_weaponEnable 0` restores ~400 ms
- [x] MP40 hold unchanged at `cod_autoFireScale 1`
- [x] Jump slightly lower than vanilla; AI jump/fire unchanged
- [x] Start/stop feels weightier; A/B via `/cod_menu`
- [x] Landing briefly slows move; `cg_showmiss 1` clean
- [x] `cod_enable 0` restores vanilla

Core feel confirmed in-game 2026-10-08. Follow-up below before Phase 5b (vitals), then Phase 6 (slide).

---

## 5.5 Quick knife (CoD-style, bind `V`) — follow-up

RTCW has no separate melee mode: only `WP_KNIFE` (inventory) and unrelated foot `+kick`. Do **not** bind V to `+kick`.

**Behaviour:** press `V` → switch to knife → one auto swing when READY → return to the previous weapon. If already holding the knife, just swing once (no switchback).

**Implementation (cgame, same family as scope-hold / `toggleads`):**

| Piece | Detail |
|---|---|
| Command | `quickknife` in `cg_cod.c` + `cg_consolecmds.c` |
| Bind | `bind v "quickknife"` in `codmod_binds.cfg` (first launch / `--reset-binds`) |
| Prev weapon | Dedicated `cg.codQkPrev` — **not** `cg.switchbackWeapon` (`weaplastused`) |
| Switch | `CG_FinishWeaponChange` to/from `WP_KNIFE` |
| Swing | When `ps.weapon == WP_KNIFE` && `WEAPON_READY`: pulse `+attack` / `-attack` via console |
| Tick | `CG_CodUpdateQuickKnife()` from `CG_DrawActiveFrame` next to scope-hold |
| Timeout | `cod_quickKnifeTimeout` (~900 ms) failsafe return |
| Switch speed | `cod_knifeSwitchTime` (default **75** ms drop/raise; 0 = vanilla 250). Return starts as soon as the swing registers (no wait for knife READY) |
| Enable | `cod_quickKnifeEnable` (default 1), gated on `cod_enable` |
| Pad R3 | `+quickkick`: tap = `quickknife`, hold ≥250 ms = pulsed `+kick` (`CG_QuickKickDown_f`/`CG_CodUpdateQuickKick`) |
| Kick damage | `cod_kickDamage` (default **15** = vanilla; was 50 until 2026-10-20) in `Cmd_WolfKick_f`; keyboard `+kick` unchanged otherwise |

**Abort / edges:** dead, no knife bit, already mid-quickknife, manual weapon change mid-sequence (don't force return), death clears state. Optional `-ads` if sticky ADS was on.

### Acceptance (quick knife)

- [x] `V` with a gun: knife comes up, swings once, returns to that gun
- [x] `V` while already on knife: one swing, stays on knife
- [x] No knife / dead: no-op
- [x] Manual number-key mid-sequence: abort, keep the chosen weapon
- [x] Does not fire `+kick`
- [x] Snappy pull (`cod_knifeSwitchTime` 75) + return as soon as swing registers (confirmed 2026-10-08)

Next: [phase-5b-vitals.md](phase-5b-vitals.md).
