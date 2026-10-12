# Phase 2 — Modernized Movement (CoD4 Tuning)

**Prerequisite:** Phase 1 confirmed by the user.
**Read first:** [architecture.md](architecture.md) (especially the golden rules) and
[reference-values.md](reference-values.md).

Work in this order. Each step is one or more commits on the `iortcw` fork's `main` branch. Build
with `scripts/build.sh --game-only && scripts/install.sh` (engine untouched in this phase).

---

## 2.0 Foundations: tuning framework + debug HUD

1. Create `game/bg_cod.h` / `game/bg_cod.c` as specified in
   [architecture.md §5](architecture.md#5-tuning-cvars-cod_). Add `bg_cod.o` to both
   `Q3GOBJ_` and `Q3CGOBJ_` in `SP/Makefile`.
2. Register and update the table from `g_main.c` and `cg_main.c`.
3. Add networked state names to `bg_public.h`:
   ```c
   // codmod: networked state for CoD-style movement (stats are sent as 16-bit shorts)
   STAT_COD_ADS = 8,      // phase 3: ADS fraction * 1000
   STAT_COD_SLIDE,        // phase 4: >0 slide ms left, <0 cooldown ms
   STAT_COD_FLAGS,        // bitfield, see COD_SF_*
   ```
   (Keep them inside `statIndex_t`, after `STAT_PLAYER_CLASS`.)
   `#define COD_SF_SPRINTING 1` (more bits added later).
4. `cgame/cg_cod.c`: `cod_debugHud` overlay ([architecture.md §6](architecture.md#6-debug-hud-built-in-phase-2-extended-in-3--4)),
   plus the `cod_dump` console command (register it in `cg_consolecmds.c`'s `commands[]`).

**Check:** builds; `cod_debugHud 1` shows the live speed; `cod_dump` prints the cvars;
`cod_enable 0` vs `1` changes nothing yet.

---

## 2.1 Walk / jog / sprint speeds

### 2.1.a Player base speed — `game/g_active.c` (~L1002, `ClientThink_real`)
After `client->ps.speed = g_speed.value;` and **before** the `PW_HASTE` multiply:
```c
// codmod: CoD4 speeds for the player only (AI keeps vanilla g_speed and its own scales)
if ( !client->ps.aiChar && bg_cod.enable && bg_cod.moveEnable ) {
	client->ps.speed            = bg_cod.runSpeed;
	client->ps.runSpeedScale    = 1.0f;
	client->ps.sprintSpeedScale = bg_cod.sprintScale;
	client->ps.crouchSpeedScale = bg_cod.crouchScale;
} else if ( !client->ps.aiChar ) {
	// restore vanilla values (from ClientSpawn) so cod_enable 0 is a true A/B
}
```
These `ps` fields are networked, so prediction picks them up automatically. Re-applying
them every frame also covers savegame loads (see [architecture.md §7](architecture.md#7-savegames)).

### 2.1.b Direction & walk scales — `bg_pmove.c` `PM_WalkMove` (~L960)
For the player only (`!pm->ps->aiChar && cod move enabled`), after `scale = PM_CmdScale( &cmd );`:
- `if ( fmove < 0 ) fmove *= bg_cod.backScale;`
- `smove *= bg_cod.strafeScale;`
- Walk: when `pm->cmd.buttons & BUTTON_WALKING`, the engine already sends half-magnitude
  input (64/127 ≈ 0.504, see `cl_input.c:351`). Multiply `scale` by
  `bg_cod.walkScale * 127.0f / 64.0f` so walk speed = `runSpeed × walkScale` exactly.
  Comment the math.

### 2.1.c Sprint rework — `bg_pmove.c` `PM_CmdScale` (~L413) and `PM_Sprint` (~L3948)
Vanilla problems: drain is per call (frame-rate dependent), sprint works backwards and
sideways, and recharge is slow. For the player, when enabled:

1. New `static void PM_CodUpdateSprint( void )`, called in `PmoveSingle` **before** the
   move-type dispatch (right after `PM_DropTimers()`):
   - `wantSprint = (cmd.buttons & BUTTON_SPRINT) && (forwardOnly ? cmd.forwardmove > 0 : moving)
      && !(pm_flags & PMF_DUCKED) && waterlevel < 2 && !(cmd.buttons & BUTTON_WALKING)`
      (phase 3 adds `&& !ADS`; phase 4 adds `&& !sliding`).
   - `wasSprinting = stats[STAT_COD_FLAGS] & COD_SF_SPRINTING`
   - Start needs `sprintTime >= sprintMinTime_equiv`. Continuing needs `sprintTime > 0`.
   - Set or clear `COD_SF_SPRINTING`. This is networked, which is why we don't use the
     non-networked `sprintExertTime`.
2. `PM_CmdScale`: for the player, use the `COD_SF_SPRINTING` flag instead of
   `BUTTON_SPRINT && sprintTime > 50`.
3. `PM_Sprint`: for the player, replace the drain/recharge block with time-based math and
   keep the 0..20000 range (the HUD stamina bar in `cg_draw.c` depends on it):
   - drain: `sprintTime -= 20000 / cod_sprintTime * pml.frametime` while sprinting **and** moving (> 128 u/s, as vanilla)
   - recharge: `sprintTime += 20000 / cod_sprintRechargeTime * pml.frametime`
   - Keep `PW_NOFATIGUE` handling (stamina pickups and the `nofatigue` cheat).
   - Keep vanilla's jump stamina cost (in `PM_WalkMove` ~L940) as is, or scale it to
     `cod_sprintJumpCost` (default 2000) for the player.
   - Still set `sprintExertTime` as vanilla does (used by breathing sounds etc.), but never read it in pmove.

**Check (HUD):** jog 200 ±2, sprint 300 ±3, walk 90 ±2, crouch 130 ±2, back 140, strafe 170.
Sprint lasts ~4 s at `com_maxfps 60`, `125`, and `250`, the same at all three (frame-rate independence).
Backward + sprint = no sprint. Enemies move exactly as in vanilla (compare a patrol in `escape1` with
`cod_enable 0/1`).

---

## 2.2 Crouch transitions (~30% snappier)

How crouch works now: `PM_CheckDuck` switches the bbox and `ps->viewheight` **instantly**.
The only visible "animation" in first person is cgame's camera smoothing
(`cg_view.c` ~L628, linear over `DUCK_TIME 100` ms, set up in `cg_playerstate.c:549`).
Third-person crouch animations aren't visible to the SP player, so leave them alone.

Changes (all cgame, player-only by construction):
1. `cg_view.c` duck smoothing: replace `DUCK_TIME` with `cod_duckTime` (70 ms default) when
   enabled. With `cod_duckEase 1`, use an ease-out curve:
   ```c
   f = timeDelta / duckTime;            // 0..1
   f = 1.0f - ( 1.0f - f ) * ( 1.0f - f );   // ease-out quad
   cg.refdef.vieworg[2] -= cg.duckChange * ( 1.0f - f );
   ```
   Also update the `cg.duckTime = cg.time - DUCK_TIME` clamp right above it.
2. Optional, small: a viewmodel dip that follows the same curve
   (`CG_CalculateWeaponPosition`: `origin[2] -= duckChange * 0.1 * (1-f)`), behind
   `cod_duckGunDip` (default 1). It gives the "weight" CoD4 stance changes have.
3. The crouch move speed is already handled in 2.1 (`crouchScale 0.65`).
4. **Prone:** not in this phase. It is phase 6b ([phase-6b-prone.md](phase-6b-prone.md), decision D2). Keep the duck-smoothing code easy to extend with a per-transition duration (`cg.codDuckDuration`), because 6b reuses it.

**Check:** tap crouch repeatedly. It feels quicker than `cod_enable 0` with no visible pop.
Stand up under a low ceiling is still blocked. `cg_showmiss 1` prints nothing new while crouch-spamming.

---

## 2.3 Lean / peek

Vanilla (`bg_pmove.c` ~L3566-3660, `cg_view.c` ~L666, `cg_weapons.c` ~L1721):
offset `LEAN_MAX 28`, camera roll `leanf / 2` (≈14°), in 280 ms, out 350 ms, no firing,
no crosshair, and the gun pitched down.

1. **pmove** (`PM_UpdateLean`, already returns early for AI): replace the constants with
   `bg_cod.leanMax`, `leanTimeIn`, `leanTimeOut` when enabled (32 / 200 / 180).
   The function also runs from `PM_UpdateViewAngles` with `pm == NULL` (tpm path, see the
   `if ( pm ) … else tpm->trace` code). Read only `bg_cod`, not `pm`, for the values.
2. **Allow firing while leaned** (`cod_leanAllowFire 1`):
   - `PM_UpdateLean`: don't zero `leaning` on `EF_FIRING` when allowed.
   - `PM_Weapon` ~L3098: skip the "player is leaning - no fire" return when allowed.
   - `g_weapon.c` ~L1517 already offsets the muzzle by `leanf`, so shots come from the peeked
     position. Verify.
   - `cg_draw.c` ~L2415 / ~L2598: show the crosshair while leaning when allowed.
   - `cg_weapons.c` ~L1756: drop the "pitch the gun down to show firing is not allowed"
     line when allowed.
3. **Camera tilt** (`cg_view.c` ~L669): `refdefViewAngles[ROLL] += leanf * cod_leanRollScale`
   (0.6 → ~19° at 32 u). With `cod_leanEase 1`, apply smoothstep to the *displayed*
   fraction (`s = |leanf|/leanMax; s = s*s*(3-2s)`) for roll and offset, so peeking
   accelerates and settles. This is cgame-only, so it can't affect prediction.
4. **Viewmodel counter-roll** (`cg_weapons.c` ~L1751) uses `leanf / (leanscale*2)`. Scale it
   with the same roll factor so the gun stays relatively level with the new tilt.

**Check:** peeks feel faster and tilt more; return-to-center is quick; shooting while
leaned hits where the crosshair is (test on a wall: bullet marks at the crosshair);
AI leaning is unchanged (AI never leans via pmove anyway).

---

## 2.4 Soldiers move like the player (user request, `cod_aiSpeedMode`)

The user asked: "what if soldiers could walk and run too as me?" Facts first:

- AI speeds don't come from one place. `AICast_Think` (`ai_cast_think.c` ~L626-652) **re-reads
  them every think** from the current anim's `moveSpeed` (`ANIM_MT_WALK/WALKCR/RUN` of the AI's
  state), into `cs->attributes[WALKING_SPEED/CROUCHING_SPEED/RUNNING_SPEED]`. The table in
  `ai_cast_characters.c` (soldier: run 220, walk 90, crouch 80) is only the starting value.
- cgame already plays legs animations faster or slower to match real speed
  (`cg_players.c` ~L1969-1990, `animSpeedScale = moveSpeed / anim->moveSpeed`), so changing
  AI speed doesn't cause much foot sliding.
- With CoD4 player numbers, soldiers are **already close** to the player: walk 90 = 90, run ~220
  vs jog 200. The real differences: the player can sprint (300) and crouch-walks faster (130 vs 80).

So "soldiers move like me" means:

1. **Speed match** (this step). New server-only code, right after ~L652 in `ai_cast_think.c` and
   after the spawn-time setup at `ai_cast_characters.c:1464`. For **human** characters only
   (`AICHAR_SOLDIER, AMERICAN, ELITEGUARD, BLACKGUARD, VENOM, PARTISAN, CIVILIAN, FROGMAN`, and
   the `STIMSOLDIER*` types after a check of their anims). Never zombies, lopers, super/proto
   soldiers, Helga or Heinrich, whose speeds are part of their boss/monster design:
   - `cod_aiSpeedMode 0`: vanilla.
   - `cod_aiSpeedMode 1` (**default**): match. `RUNNING_SPEED = cod_runSpeed`,
     `WALKING_SPEED = cod_runSpeed × cod_walkScale`, `CROUCHING_SPEED = cod_runSpeed × cod_crouchScale`.
     Then recompute `ps.crouchSpeedScale` as the vanilla line does.
   - `cod_aiSpeedMode 2`: scale. Multiply the anim-derived values by `cod_aiSpeedScale`.
   This is the **only** deliberate AI change in the mod. It lives in `ai_*.c` (qagame only),
   never in `bg_pmove.c`, so prediction and golden rule 1 are untouched (see
   [architecture.md §3](architecture.md#rule-1--gate-everything-on-the-player-not-on-ai)).
2. **AI sprint**: soldiers sprinting while charging or running to cover. That is new AI behaviour,
   not a number change. It's in [phase-7-extras.md](phase-7-extras.md) (E13). Jump/inertia/pistol fire are phase 5 ([phase-5-feel.md](phase-5-feel.md)).

Risks to check:
- Scripted sequences (`*.ai` scripts) that rely on an AI reaching a spot in time (e.g. a guard
  running to an alarm). The slower soldier run (200 vs ~220) makes them ~10% later.
- AI code has speed thresholds (`ai_cast_funcs.c` ~L209, ~L753, ~L2971 `> 170`, ~L3034 `> 140`).
  Matched speeds stay on the same side of each threshold for soldiers (run 200 > 170). Re-check if
  the user tunes `cod_runSpeed` below ~180.
- Crouch-walk anims play 1.6× faster at 130. If it looks silly, use mode 2 or lower only crouch.

**Check:** add the nearest AI's horizontal speed and `aiState` to the debug HUD
(`cod_debugHud 2`, read from `cg_entities` like `CG_PlayerAnimation` does). Patrols walk at 90,
alerted soldiers run at 200, crouching soldiers move at 130 in mode 1. With `cod_aiSpeedMode 0`,
the vanilla values come back. Play the `escape1` alarm sequence in both modes.

---

## Acceptance criteria (gate)

- [ ] All checks above pass. HUD speeds match [reference-values.md](reference-values.md) defaults.
- [ ] `cod_enable 0` restores vanilla feel in the same session.
- [ ] No new `cg_showmiss` prediction errors during: sprint start/stop, stamina empty,
      crouch spam, lean spam, walk toggle.
- [ ] With `cod_aiSpeedMode 0`: AI movement unchanged. Play the first area of `escape1` and watch patrols and chases.
- [ ] With `cod_aiSpeedMode 1`: human AI speeds match the player's (HUD), monsters unchanged, scripted sequences still complete.
- [ ] Savegame made in this phase loads correctly. A vanilla-era codmod save also loads.
- [ ] No new compiler warnings in touched files.
- [ ] Phase report to the user: list of cvars + defaults, how to tune (`cod_debugHud 1`,
      `cod_dump`), known limits (gait presentation is phase 4; prone comes in phase 5b). Then **stop**.
