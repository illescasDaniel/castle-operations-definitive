# Tactical AI overhaul (F.E.A.R.-style soldiers)

Goal: human enemies that use cover, pop out to shoot, crouch, move around corners, coordinate as a squad, flank,
flush the player out with grenades and search intelligently when they lose contact. Monsters, bosses and scripted
sequences keep their original behaviour.

Phase gating as usual: each phase is built, smoke-tested, reported, and **waits for the user's in-game check**
before the next starts. Status is tracked in `memory/progress.md`.

## 1. Why the current AI feels stupid (diagnosis)

Read from `iortcw/SP/code/game/ai_cast_*.c` (Ridah's 2001 cast AI):

| Behaviour | Code | Problem |
|---|---|---|
| Fighting | `AIFunc_Battle` (`ai_cast_funcs.c`) | Stands still in the open and fires. The combat-move block (`AICast_CombatMove`) is commented out, so there is no strafing or repositioning while shooting. Crouch is a one-off coin flip at battle start (`ATTACK_CROUCH`). |
| "Cover" | `AICast_GetTakeCoverPos` (`ai_cast_fight.c`) → botlib `AAS_NearestHideArea` | Returns the nearest AAS area waypoint that is **fully hidden** from the enemy. That is a hiding spot, not cover: from there the AI cannot shoot. It waits on a timer (`takeCoverTime`) and then charges back out (`AIFunc_DefaultStart` → chase). No concept of low cover, corners or peeking. |
| When to hide | `AICast_WantsToTakeCover`, `AICast_Aggression` | Pure aggression/health/pain arithmetic plus a time-based "ambush" sine. Not driven by the tactical situation. |
| Squad | `AIVIS_SHARE_RANGE` (384) in `ai_cast_sight.c` | Only shares sightings with friends within 384 units. No roles, no coordination; every soldier attacks at once or hides at once. |
| Under fire | `AICast_ProcessBullet` | Ignores near-miss bullets once in combat (`aiState >= AISTATE_COMBAT → continue`). No suppression. |
| Grenades | `AIFunc_GrenadeFlush`, global `lastGrenadeFlush` | Throws on a 7 s global cooldown whenever the enemy is out of sight. Not tied to "player is camping behind cover". |
| Lost contact | `AIFunc_BattleChase` / `AIFunc_BattleHunt` | Runs straight to the last seen position. No cautious approach, no corner checking, no holding angles. |

## 2. What the engine gives us (constraints)

- **Animations** (`models/players/infantryss/wolfanim.cfg`, shared by soldiers): stand/crouch idle and fire,
  `alert_crch_*` (crouch walk), `alert_bk_*`/`firing_bk_*` (backpedal), `firing_strafe_*_L/R` (strafe while firing),
  `firing_run_*`, `diving`, `kick`, `kick_bk`/`throw_bk` (grenade throw-back), `jump_*`, `climb_*`.
  **No lean animations** and no blind-fire. Peeking is done by stepping out of a corner or standing up from low
  cover. (A lean could be faked with a cgame torso roll; optional, Phase 5.)
- **AI movement**: bots drive a `usercmd_t` (`AICast_InputToUserCommand`), so crouch = `attackcrouch_time`,
  movement direction is world-space (`trap_EA_Move` / `AICast_MoveToPos`) and independent from the view, so an AI can
  aim at the player while strafing or backing up. Speed via `cs->speedScale`; sprint via `AICast_CodTrySprint`.
- **Navigation**: AAS (botlib). Game-side syscalls: `trap_AAS_PointAreaNum`, `trap_AAS_AreaTravelTimeToGoalArea`
  (travel time in 1/100 s, 0 = unreachable), `trap_AAS_TraceAreas`, `trap_AAS_RT_GetHidePos`,
  `trap_AAS_FindAttackSpotWithinRange`, `trap_AAS_GetRouteFirstVisPos`, plus `AICast_PredictMovement`. botlib is in
  the fork, so new AAS queries are possible, but they need a full engine build; prefer game-side sampling.
- **Voice barks** (`sound/scripts/ai.sounds`): soldiers only have `infantryAttackPlayer` (3 lines),
  `infantryOrders` ("Angriff!", "Schnell!", ...), inspect/hmm/nada lines, pain, death. Enough for "attack/advance"
  and "move!" callouts; no "grenade!" line (new recorded/TTS lines are an optional extra).
- **Savegames**: `cast_state_t` is written as a raw struct (`WriteCastState`, `g_save.c`), so **new state must not
  go into `cast_state_t`**. Use static arrays (like `codAiSprintUntil[]`), which a load simply resets.
  Every new `AIFunc_*` that can be stored in `cs->aifunc`/`cs->oldAifunc` **must be listed in `g_funcs.h` and
  `g_func_decs.h`**, or saving errors out ("unknown function, cannot save game").
- **Level scripts** (`maps/*.ai`) drive many soldiers (`nosight`, `noattack`, `gotomarker`, `attack`, `camper`
  attributes, `denyactivate`, ...). Tactical code must step aside whenever a script is in control.

## 3. Architecture

New files (game module, so `scripts/build.sh --game-only --install` is enough unless a phase says otherwise):

- `ai_cast_cod.h` – shared types and prototypes.
- `ai_cast_cod.c` – eligibility, per-AI tactical state, the combat state machine (`AIFunc_CodCombat`), debug.
- `ai_cast_cod_cover.c` – cover finder and cover claims.
- Later phases: `ai_cast_cod_squad.c` (squads, roles, tokens, callouts), `ai_cast_cod_search.c` (lost contact).

Add the new `.c` files to every build list that compiles `ai_cast_fight.c` (Makefile / CMake in `iortcw/`).

**One entry point.** Vanilla functions get a two-line router at the top, nothing else:

```c
if ( AICast_CodTacticsActive( cs ) ) {   // codmod: tactical AI
    return AIFunc_CodCombatStart( cs );
}
```

placed in `AIFunc_Battle`, `AIFunc_BattleTakeCover` and `AIFunc_BattleChase` (after their danger/door checks).
Everything vanilla stays reachable: when tactics are off or the AI is not eligible, the original code runs
unchanged, so `cod_optTactics 0` is a true A/B.

**Eligibility** `AICast_CodTacticsActive( cs )`, all must hold:

- `bg_cod.enable && bg_cod.aiTactics` (cleared by `cod_optTactics 0` in `BG_CodApplyOptions`).
- Human soldier types only: `AICHAR_SOLDIER, AMERICAN, ELITEGUARD, BLACKGUARD, PARTISAN, FROGMAN`
  (not civilians, Venom, stim/proto/super soldiers, zombies, lopers, bosses). `cs->aasWorldIndex == 0`.
- Has an enemy that is alive, a usable bullet weapon (not `WP_MONSTER_*`, flamethrower, Venom, Tesla, sniper rifles,
  `AIFL_ZOOMING`), not mounted on an MG42, not following a leader (`leaderNum < 0`).
- No script in control: `castScriptEventIndex < 0`, `scriptNoMoveTime < level.time`, `scriptNoAttackTime <
  level.time`, `scriptGotoEnt < 0`, no `AIFL_DENYACTION`/`AIFL_SPECIAL_FUNC`, `pauseTime < level.time`.
- `attributes[CAMPER] < 0.5` (campers keep their post; Phase 5 lets them crouch-peek in place).
- The enemy was seen recently (`vislist[enemy].real_visible_timestamp > level.time - cod_aiMemoryTime`), and
  `codAI[n].noTacticsUntil < level.time` (a back-off so hand-overs to vanilla chase/hunt cannot loop).

**State**: `static codAI_t codAI[MAX_CLIENTS]` in `ai_cast_cod.c`. Reset on spawn/death/map load (zeroed when
`codAI[n].spawnCount` differs from a counter bumped in `AICast_CreateCharacter`/respawn, or simply when the AI is
dead), and implicitly after a savegame load (static memory is zero / stale-safe because every sub-state validates
its own data and restarts when invalid).

**Cvars** (table in `bg_cod.c`, values in `codmod_tuning.cfg`, regenerated with `scripts/gen-cod-tuning.py` if
that is how the table is kept in sync): `cod_aiTactics` (internal master, 1), `cod_aiDebug` (0),
`cod_aiMemoryTime`, `cod_aiCoverRadius`, `cod_aiCoverMaxTravel`, `cod_aiCoverSearchesPerFrame`, peek/hide timing
ranges, strafe timing. User-facing toggle `cod_optTactics` ("Tactical Enemies", GAMEPLAY menu, archived, code default
0, `seta cod_optTactics 1` in `codmod_defaults.cfg`), documented in `docs/gameplay-options.md`.

**Debug** `cod_aiDebug 1`: console line per tactical state change (`[ai] <aiName> OPEN->MOVE cover=LOW d=312`).
`cod_aiDebug 2`: also draw the chosen cover (and peek spot) with short-lived debug lines/rail trails visible to the
player. Must be cheap when 0.

**Performance budget**: cover searches are rationed globally (`cod_aiCoverSearchesPerFrame`, default 1 per server
frame); an AI that cannot search this frame keeps its current behaviour and retries next think. A search is at most
~48 candidates × ~6 traces.

## 4. Phases

### Phase 1 – Cover and fighting from cover (single soldier)

The biggest visible change: soldiers stop standing in the open.

**1a. Cover finder** (`ai_cast_cod_cover.c`): `qboolean AICast_CodFindCover( cast_state_t *cs, vec3_t threatPos,
int threatNum, int mode, codCover_t *out )`, modes `COVER_ATTACK` (wants a spot it can shoot from) and `COVER_HIDE`
(fully hidden, for reloading/retreating). Game-side sampling, no map data needed:

1. Candidates (≤ 48): (a) wall-hug rays: 16 directions from the AI, hull trace (AI bbox) up to `cod_aiCoverRadius`
   (768); where it hits a near-vertical surface, the end point is a candidate (spots next to walls/crates are where
   cover is). (b) Ring samples at 128/256/384/512 units, 8 angles, biased away from the threat.
2. Validate: drop to floor (hull trace down 128); reject start-solid / no ground / water; `trap_AAS_PointAreaNum`
   nonzero; reachable with `trap_AAS_AreaTravelTimeToGoalArea( cs->bs->areanum, origin, area, cs->travelflags )` in
   `(0, cod_aiCoverMaxTravel]` (300 = 3 s); not within 64 u of another living AI's claimed cover or body; not near a
   live danger entity (grenade).
3. Classify against the threat's eye (`threatPos + DEFAULT_VIEWHEIGHT`), `trap_Trace` with `MASK_SHOT &
   ~CONTENTS_BODY`-style mask ignoring the two actors:
   - stand eye (`+40`) and crouch eye (`+16`, plus a body point `+8`) both blocked → hidden. Then try lateral peek
     offsets perpendicular to the threat direction at 32 and 48 u (hull trace must reach them): if the stand eye at
     the offset sees the threat → **CORNER_L/R** (`peekPos` = that offset); otherwise **FULL** (hide-only).
   - stand eye sees, crouch eye and body blocked, and the blocking surface is within 96 u of the spot → **LOW**
     (crouch to hide, stand to shoot).
   - visible crouched → not cover.
4. Score (higher is better): type weight (ATTACK: LOW = CORNER = 1.0, FULL = 0.3; HIDE: FULL = 1.0, others 0.6),
   minus travel time, minus a penalty when closer than 192 u to the threat, a preference band per weapon
   (SMG 256–900, rifle 400–1500, pistol 200–700), a penalty when the route heads toward the threat (spot closer to
   the threat than the AI *and* in front of it), and a bonus for height advantage (≤ 96 u above the threat).
   Best candidate wins; it is claimed (`codCoverClaims`), and released on death/new cover.

**1b. Combat state machine** `AIFunc_CodCombat` (one AIFunc, internal sub-states, so only `AIFunc_CodCombat` and
`AIFunc_CodCombatStart` need save-table entries). Before the sub-states it repeats the vanilla checks it replaces:
danger entity → `AIFunc_AvoidDangerStart`; door marker; enemy dead → `AIFunc_InspectBodyStart` /
`AIFunc_DefaultStart`; no ammo at all → vanilla; `!AICast_StopAndAttack` → vanilla chase; the vanilla grenade-flush
condition (moved into a shared helper so both paths use it); not eligible any more → `AIFunc_DefaultStart` with a
short `noTacticsUntil` back-off.

Sub-states:

- **OPEN** – no cover yet. Fire while combat-strafing: pick left/right every 0.6–1.4 s, keep the strafe only if a
  hull trace/predict says the AI stays on ground and keeps line of fire; random short crouch bursts weighted by
  `ATTACK_CROUCH`. Request a cover search every think (rationed). Pain or a low magazine makes the search urgent
  (bypasses the ration once).
- **MOVE** – run (sprint if > 200 u, `AICast_CodTrySprint`) to `cover.pos`; aim and fire on the move when
  `AICast_CanMoveWhileFiringWeapon` and the shot is clear (the vanilla take-cover code shows how:
  `AICast_MoveToPos` + `AICast_ProcessAttack`). Abort and re-search on `moveresult->failure/blocked`, on timeout
  (2 × travel time + 1 s), or when the spot becomes visible from the threat's *current* position while still far.
- **HIDE** – at the spot: crouch for LOW cover; for CORNER stay on the hidden spot. Face the threat's last known
  position. Reload here if the magazine is below half. Stay 0.6–1.8 s (shorter with higher `AGGRESSION`).
  If the threat can now see/shoot the AI at its hidden spot → **compromised**: re-search (`COVER_ATTACK`).
- **PEEK** – LOW: stand up; CORNER: step to `peekPos` (`AICast_MoveToPos`, `speedScale` ~0.6). Fire a burst for
  1.0–2.5 s once the line of fire is clear (`AICast_ProcessAttack`). Back to HIDE when the burst ends, when hit
  during the peek, or on an empty magazine. After 3–5 peek cycles, or if the threat moved more than 256 u from the
  position the cover was chosen against, re-search.
- Lost sight: if the enemy has not been visible from the peek for 2.5 s, hand over to vanilla
  `AIFunc_BattleChaseStart` and set `noTacticsUntil = level.time + 3000` (Phase 4 replaces this).

**1c. Plumbing**: router lines, eligibility, cvars + `cod_optTactics` menu row (codmod layer, `docs/menus.md`
workflow, export the delta), `g_funcs.h`/`g_func_decs.h` entries, debug output, docs.

**User check (Phase 1)**: `escape1` → `escape2`, Normal skill, `cod_aiDebug 1`. Soldiers should run to walls,
crates and doorframes when they see you, crouch behind low cover and stand to shoot, step out from corners, duck
back when you hit them, reload out of sight, and strafe instead of standing still when caught in the open.
`cod_optTactics 0` must restore the old behaviour. Scripted moments (cell guard, cutscenes, MG42 gunners) unchanged.
Save/load in the middle of a fight works.

### Phase 2 – Squad tactics

- **Squads**: dynamic grouping each second: alive, eligible AIs of the same team fighting the same enemy within
  1200 u and in PVS of each other. Squad blackboard: shared last known threat position/time (one soldier seeing the
  player updates everyone, replacing the 384 u share for squad members), member roles, current orders.
- **Attack tokens** (fairness, F.E.A.R./Halo style): at most N soldiers (`cod_aiAttackTokens`, by skill 2/3/4) may
  shoot at the player at the same time; others hide, reposition, or flank. Tokens rotate every few seconds.
- **Fire and move** (bounding overwatch): only one or two members relocate at a time; the rest fire from cover.
  Movers advance cover-to-cover (`COVER_ADVANCE` mode: peekable cover that is closer to the threat).
- **Flanking**: when the player holds one spot for more than ~6 s, the squad picks a flanker that searches for
  cover whose bearing to the player differs from the squad's mean bearing by > 60°, routed along spots not visible
  from the player (sample route points with `trap_AAS_GetRouteFirstVisPos` / visibility traces).
- **Suppressive fire**: while a teammate moves, a token holder fires at the player's cover edge / last known
  position for 1–2 s even without a clean shot (aim at the point where a trace towards the last known position
  hits, if it lands within 64 u of it).
- **Callouts**: rate-limited barks via the existing sound scripts (`ORDERSSOUNDSCRIPT` when a flank/advance order is
  given, `ATTACKSOUNDSCRIPT` when a mover starts); one speaker per squad per few seconds.

**User check**: groups of 3+ soldiers (escape2 courtyard, castle) should not all shoot at once, move up in turns,
and try to get around the player who camps behind one crate.

**Implemented (Phase 2)**: `ai_cast_cod_squad.c` (new, in the Makefile `Q3GOBJ_` list), hooks in `ai_cast_cod.c`,
`COVER_ADVANCE` / `COVER_FLANK` in `ai_cast_cod_cover.c`, nine internal tuning cvars (`bg_codCvars[]`, values in
`codmod_tuning.cfg`; everything is off with `cod_optTactics 0`, squads alone with `cod_aiSquad 0`):

| cvar | default | meaning |
|---|---|---|
| `cod_aiSquad` | 1 | squad layer switch |
| `cod_aiAttackTokens` | 0 | shooters per squad; 0 = auto by `g_gameskill` easy/medium/hard = 2/3/4 |
| `cod_aiTokenTime` | 3500 | ms a holder may keep the token while someone waits |
| `cod_aiSquadRange` | 1200 | u, max distance to a squad member (plus PVS) |
| `cod_aiFlankHold` | 6000 | ms the player must hold one spot before a flanker is sent |
| `cod_aiFlankMove` | 128 | u, the player still counts as holding inside this radius |
| `cod_aiAdvanceMinDist` | 400 | u, advance hops only while the threat is farther |
| `cod_aiSuppressMs` | 1500 | ms of suppressive fire when a teammate starts moving |
| `cod_aiBarkMs` | 5000 | ms between callouts per squad |

- **Squads**: the first soldier to think after 1 s (or after a spawn/death) regroups all `AIFunc_CodCombat` soldiers
  (greedy flood fill: same `aiTeam` and enemy, within range and PVS of a member). Single soldiers are in no squad and
  behave exactly as in Phase 1. Squad state is inherited by the new squad that holds most of the old members. The
  blackboard (last position of the enemy seen by any member) replaces the soldier's own last sighting whenever it is
  newer, both for the threat position and for the "enemy seen recently" eligibility check.
- **Tokens** are short leases (renewed while shooting) rather than a fixed rotation: OPEN and PEEK need one, MOVE only
  fires with one. Waiters are served first-come-first-served, a holder gives way after `cod_aiTokenTime` and never
  retakes at once. Without a token in OPEN a soldier does not fire, strafes (also with weapons that cannot fire on the
  move) and searches cover at a faster rate; if no cover is found after 3 searches it fights anyway. In HIDE it
  stays down longer, advances (below) after 2.5 s of waiting and re-searches cover after 6 s.
- **Fire and move**: voluntary relocations take a mover slot (1 per squad, 2 with 4+ members). From HIDE a soldier that
  has peeked once, with a far threat and a teammate in cover to watch, rolls (25-65 % by AGGRESSION, once a second)
  for a `COVER_ADVANCE` hop: peekable cover at least 96 u closer to the threat but not within 192 u, travel <= 70 % of
  `cod_aiCoverMaxTravel`, bonus for progress. Forced relocations (hit, exposed) are never limited.
- **Flanking**: the squad update orders one member (preferring one that is in cover and not shooting) when the
  threat has stayed within `cod_aiFlankMove` of its anchor for `cod_aiFlankHold` and was seen in the last 3 s. The
  order is picked up when the soldier is next in HIDE with a free mover slot: `COVER_FLANK` samples 24 ring points around
  the player (65-140 degrees off the squad's bearing, 0.7-1.3 x distance) plus wall-hug rays, requires >60 degrees
  difference from the squad centre's bearing, allows twice the travel time, and subtracts 8 per visible sample
  of the straight line to the spot (4 samples, traced from the player's eye). Cooldown 15 s, 8 s after a failed search.
- **Suppression**: when a mover starts, a window of `cod_aiSuppressMs` opens. A token holder in HIDE leaves cover early
  for a 1-2 s PEEK; when the player is not visible it aims where a trace to the last known position ends (only if that
  is within 64 u of it, and no teammate is in the way) and fires bursts (`CodSuppressFire`).
- **Callouts**: `ORDERSSOUNDSCRIPT` for a flank order, `ATTACKSOUNDSCRIPT` for an advance, through
  `EV_GENERAL_SOUND` like the vanilla code; one speaker per squad per `cod_aiBarkMs` (+-25 %).
- **Debug** (`cod_aiDebug 1`): state lines now read `[ai] <name> sq<id>/<ROLE> OPEN->MOVE ...` (ROLE = SOLO, FIRE, COVER,
  MOVE, FLANK), plus `sq<id> members=..`, `token granted/denied/rotated out`, `FLANK ordered / starts moving /
  in position / found no route`, `ADVANCE starts moving`. All rate-limited.
- **Deviations**: flank route visibility is sampled on the straight line to the spot (not along the AAS route;
  `trap_AAS_GetRouteFirstVisPos` answers a different question); tokens are leases rather than a rotation timer;
  skill mapping is 0/1/2 (easy/medium/hard) as in `gameskill_t`, not 1/2/3; the squad update is driven by the combat
  function itself, so no vanilla file was touched beyond the Phase 1 hooks. Not play-tested in a real fight yet
  (the smoke run only loads the map).

### Phase 2b – Push for an angle (implemented)

Problem: the player goes prone behind a table; soldiers shoot and take cover but nobody moves to get an angle.
The Phase 2 flank needs a held spot plus a recent sighting and tests spots from a standing eye. All of this is gated
by `bg_cod.aiTactics` and `cod_aiPush`; scripted characters stay on vanilla code.

**Behaviour**

- **No-shot detection.** Each soldier and each squad accumulates "tried without a real shot" time: a token holder in
  PEEK/OPEN calls `AICast_CheckAttack`; a miss adds the elapsed time (capped at 250 ms per call), a hit resets it.
  Hiding time is not counted. At `cod_aiNoShotTime` (4000 ms) the push is wanted, provided the enemy position is
  fresh (own or squad sighting within ~3 s, or the player barely moved, 96 u).
- **Body-aware targets.** `AICast_CodBodyPoints` takes points (head/chest/feet) from the enemy's current bbox, so a
  prone player (maxs z 16) is aimed at low. `AICast_CodBodyShot` tests a clear `COVER_MASK` line from an eye to any
  point. The FLANK and ADVANCE spot tests use it too.
- **Angle search (`COVER_ANGLE`).** Threat-ring candidates at radii 160/288/416 with 8-12 angles plus the soldier
  ring (up to 72 candidates). A spot needs a body-point line from a stand or crouch eye. Scoring prefers crouch shots,
  low cover/corner, closer distance (not under ~128 u unless pistol/SMG), a bearing change, short travel (max 2x
  `cod_aiCoverMaxTravel`) and a route outside the player's line of fire. Claims, avoidPos, dangers and the search
  ration are respected. Types: LOW/corner reuse the HIDE/PEEK flow; exposed spots are the new `COVER_FIRE`.
- **Who pushes.** In a squad one soldier pushes (two with 4+ members), role `PUSH`, using the mover-slot machinery and
  an ORDERS bark. The others keep their tokens and suppress; the suppression window is extended for the run, capped
  ~4 s. Squad cooldown `cod_aiPushCooldown` (9000 ms, halved after a failed push). A solo soldier pushes itself.
- **Arrival.** A LOW/corner spot uses HIDE/PEEK, the peek validated against the body points. An exposed spot fires at
  once (crouching when the crouched eye has the shot, no strafe). Pushers get token priority. No shot after ~2.5 s
  avoids the spot and a later push is allowed.
- **Fallbacks.** No angle: a grenade flush (`AICast_WantsGrenadeFlush`), else a COVER_ADVANCE hop that ignores
  `cod_aiAdvanceMinDist` but stays out of the final 192 u.
- **Debug.** `cod_aiDebug 1` prints rate-limited lines (`PUSH no shot for N ms -> angle spot d= ... travel=`, `PUSH no
  angle, advance|grenade`, `PUSH arrived, shot ok|none`); `cod_aiDebug 2` draws the spot like other cover.

**Files:** `bg_cod.h/.c` (cvars), `ai_cast_cod.h`, `ai_cast_cod.c` (push state machine hooks), `ai_cast_cod_cover.c`
(body points, `COVER_ANGLE`), `ai_cast_cod_squad.c` (no-shot clocks, pusher choice, API), `mod/codmod/codmod_tuning.cfg`.
No new `cast_state_t` fields and no new `AIFunc_*`; all state is in static stale-checked arrays.

| Cvar | Default | Meaning |
| --- | --- | --- |
| `cod_aiPush` | 1 | Enable pushing for an angle |
| `cod_aiNoShotTime` | 4000 | Ms of trying without a shot before a push |
| `cod_aiPushCooldown` | 9000 | Squad cooldown between pushes (ms) |

**Deviations:** the pusher's bark fires when it starts moving, not at order time; exposed spots needed a new
`COVER_FIRE` type and `angle`/`crouchShot` fields in `codCover_t`; the cooldown is halved after a failed push; the
enemy stance is read from its real bbox and the "barely moved" test uses the player's true position (small cheats).
Not play-tested in a real fight yet.

### Phase 3 – Threat reactions

- **Grenades, offensive**: throw when the player has stayed behind the same cover for > 4 s or is out of sight
  behind a known corner; check the arc (existing `AICast_SafeMissileFire`), squad-wide cooldown instead of the global
  one, callout.
- **Grenades, defensive**: improve `AIFunc_AvoidDanger`: run out of the blast radius along a direction that leads
  away from the grenade *and* to cover (`COVER_HIDE` with the grenade as threat); dive when the character has
  `AIFL_DIVE_ANIM`; make sure soldiers with `AIFL_CATCH_GRENADE` use the existing `AIFunc_GrenadeKick` throw-back.
- **Suppression**: count near misses (`AICast_ProcessBullet`, also in combat) into a decaying suppression value;
  suppressed AIs stay hidden longer, peek less, shoot less accurately; suppressed AIs in the open run for cover.
- **Pain**: being hit in the open → cover; low health → `COVER_HIDE` farther away (retreat).
- **Morale**: when a squad loses half its members, survivors fall back to cover farther from the player and regroup.
- **Opportunism**: player reloading / switching weapons / in a slide or prone → the token holders push or peek
  immediately ("Schnell!").

### Phase 4 – Search and hunt (lost contact)

- Replace the hand-over to vanilla chase: the squad moves to the last known position cover-to-cover, with one
  member covering. The predicted position (last known position + last velocity × time) is the search target.
- **Corner clearing** ("slice the pie"): approach corners wide, aim at the corner edge while strafing around it,
  crouch-walk the last stretch.
- **Hold angles**: one or two members stay in cover aiming at the door or corridor the player left through.
- Search sweep over nearby AAS areas the player could have reached (travel time from last known position), then a
  heightened-alert return (query state, faster reaction) instead of forgetting.

### Phase 5 – Movement and aim polish

- Backpedal while firing when the player charges (`firing_bk_*`), crouch-walk between low covers, short jinks
  under fire, kick when the player is in melee range (`kick` anim, existing kick damage).
- Accuracy model: first shots of an engagement go wide (warning), accuracy grows with time in sight, drops when the
  player sprints/slides or the AI is moving or suppressed. Scaled by skill.
- Campers (`CAMPER` attribute): crouch-peek in place.
- Optional: fake lean for AIs (torso roll in cgame driven by a small entityState field) if the step-out peek looks
  too stiff. Optional: new voice lines ("Granate!", "Flankieren!").

### Phase 6 – Difficulty, performance, regression

- Scale tokens, reaction times, peek lengths and flanking frequency by `g_gameskill`.
- Profile traces per frame with many AIs (cvar counter in the debug line); keep the budget.
- Full-campaign regression: every map's scripted sequences, friendly AIs (partisans, village), MG42 gunners,
  snipers, bosses untouched, save/load mid-fight, `cod_optTactics 0` A/B.
- Final docs (`docs/ai-tactics.md`) and tuning values.

## 5. Implementation process

Each phase is implemented by a Sonnet subagent from the spec above, then reviewed (diff read, build, smoke run) by
the main agent before the user's in-game check. Engine/game code changes are committed in the `iortcw/` submodule
and pushed to the fork, then the outer repo bumps the pointer, only when the user asks.
