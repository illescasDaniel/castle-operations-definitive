# Tactical AI overhaul (F.E.A.R.-style soldiers)

Goal: human enemies that use cover, pop out to shoot, crouch, move around corners, coordinate as a squad, flank,
flush the player out with grenades and search intelligently when they lose contact. Monsters, bosses and scripted
sequences keep their original behaviour.

Finished-system overview, cvar reference and difficulty table: [ai-tactics.md](ai-tactics.md).

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

**Implemented (Phase 3)** (not play-tested in a real fight yet). All of it is gated by `cod_optTactics` and runs only
for soldiers in `AIFunc_CodCombat`; scripted and special characters stay on vanilla. State is in static stale-checked
arrays (`codAI[]`, `codSupp[]`, the squad/member tables); no `cast_state_t` fields, no new `AIFunc_*`.

- **Offensive grenades** (`CodGrenadeWanted`). Thrown when the threat stayed within 96 u of one spot for
  `cod_aiGrenadeHold` ms and nobody had a real shot for 1.5 s, or when it is out of sight behind a known corner (seen
  there for 1.5 s, no line from the soldier). One thrower per squad (`AICast_CodGrenadeScore`: carries one, 200-1100 u,
  a cheap lob test; nearest wins), squad cooldown `cod_aiGrenadeCooldown` (+-15 %) with an ATTACK bark, a solo soldier has
  its own cooldown, nobody while a squad mate pushes for an angle. The throw itself is the vanilla `AIFunc_GrenadeFlush`,
  which repeats the real trajectory test (`AICast_SafeMissileFire`) before it lets go. It replaces the old
  `AICast_WantsGrenadeFlush` call in CodCombat; the Phase 2b push fallback uses the same cooldown and thrower choice.
- **Defensive grenades** (`CodDanger`). A grenade danger is handled here, everything else (flames, dynamite, ...) still
  goes to the vanilla `AIFunc_AvoidDanger`. Soldiers with `AIFL_CATCH_GRENADE` kick it back with `AIFunc_GrenadeKick`
  under the vanilla rules (fuse > 1.5 s, reachable in time, one per 3 s, not a friend's). Otherwise: stay when the spot
  is covered from the landing point or outside the blast; else a `COVER_DODGE` search (hidden from the landing point,
  urgent, travel capped at the fuse minus 0.5 s, running at the grenade penalised), sprint there, no shooting, and a dive
  (`AIFunc_BattleDiveStart`, `AIFL_DIVE_ANIM` only) when still in the blast with < 1.2 s left. At the spot it hides until
  0.5 s after the blast and then replaces the hidden-only spot with an ordinary attack spot. No dodge cover: the vanilla
  avoid, as before. Each grenade is reacted to once.
- **Suppression.** `AICast_ProcessBullet` calls `AICast_CodNoteBullet` for AIs already in combat: an enemy bullet passing
  within 160 u adds 0.12-0.32 to a 0..1 value that decays by `cod_aiSuppressDecay` per second. At
  `cod_aiSuppressThreshold` the soldier is suppressed: hides up to 80 % longer (and keeps hiding while near misses go on,
  max 3.5 s), peeks up to 45 % shorter, and `AICast_GetAccuracy` is multiplied by `1 - 0.55 v` (about 0.45-0.72). A
  suppressed soldier in OPEN does an urgent cover search every 250 ms.
- **Pain.** Hit in the open: the cover search runs at once and bypasses the ration. Health below `cod_aiRetreatHealth` %
  and hit within 3 s: an urgent `COVER_RETREAT` search (attack-type spot at least 80 u farther from the threat, up to
  1.5x the usual travel, prefers a route out of the player's sight), longer hide on arrival, then it fights from there
  (10 s cooldown).
- **Morale.** The squad tracks its peak size and losses (kept over regroups). When the dead reach half of a peak of
  3+ the survivors break for 9 s (squad cooldown 15 s): once each they bark (ORDERS) and retreat like at low health
  (`COVER_RETREAT`, hide 1.5x), then hide 1.4x longer, aggression x0.35 (hide time, advance chance), no flank, advance or
  push. A lone survivor of a broken squad is included (the trigger is the death, in `AICast_CodSquadForget`).
- **Opportunism.** The player reloading, dropping / raising a weapon, sliding, or going prone is noticed by a soldier
  that saw the player within 1 s (reload: or is within 700 u). For 0.9-1.5 s the squad gets one more attack token, token
  holders skip the rest of their hide and keep the burst going, an advance hop needs no roll, plus an ORDERS bark
  (7 s per soldier).
- **Debug** (`cod_aiDebug 1`, rate limited): `GRENADE player holds cover|behind a corner`, `GRENADE kick it back`,
  `DODGE grenade fuse= d= -> cover`, `DODGE dive`, `SUPPRESSED v=`, `HIT in the open`, `RETREAT low health|morale broken`,
  `MORALE broken (lost x of y)`, `OPPORTUNITY player reloads|slides|...`.

**Files:** `bg_cod.h/.c` (cvars), `ai_cast_cod.h`, `ai_cast_cod.c` (reactions), `ai_cast_cod_cover.c` (`COVER_RETREAT`,
`COVER_DODGE`, one-shot travel cap), `ai_cast_cod_squad.c` (thrower choice, cooldown, morale, opportunity token, solo
barks), `ai_cast_fight.c` (two gated hooks, `// codmod:`), `ai_cast.h`, `mod/codmod/codmod_tuning.cfg`.

| Cvar | Default | Meaning |
| --- | --- | --- |
| `cod_aiGrenadeHold` | 4000 | Ms the player holds one spot before a grenade (0 = no proactive grenades) |
| `cod_aiGrenadeCooldown` | 8000 | Squad / solo cooldown between thrown grenades (ms) |
| `cod_aiSuppressDecay` | 0.35 | Suppression lost per second (0 = suppression off) |
| `cod_aiSuppressThreshold` | 0.5 | Suppression value (0..1) at which a soldier counts as suppressed |
| `cod_aiRetreatHealth` | 35 | Health % below which a hit soldier retreats (0 = off) |
| `cod_aiOpportunity` | 1 | React to a reloading / weapon-switching / sliding / prone player |
| `cod_aiMorale` | 1 | Squad morale break after losing half |

**Deviations / risks:** the throw is the vanilla flush, which also walks towards the last known position while it aims, so a
thrower may leave cover; the very close "nearly stopped grenade" pickup of the vanilla avoid is not copied (only the
predicted kick); the retreat is an attack-type spot (so PEEK works there), not a pure `COVER_HIDE` spot; a dodge that
finds no cover falls back to the vanilla avoid; the player's weapon state (reload) is read directly, with the sight and
hearing limits above as the only fairness rule.

### Phase 4 – Search and hunt (lost contact)

- Replace the hand-over to vanilla chase: the squad moves to the last known position cover-to-cover, with one
  member covering. The predicted position (last known position + last velocity × time) is the search target.
- **Corner clearing** ("slice the pie"): approach corners wide, aim at the corner edge while strafing around it,
  crouch-walk the last stretch.
- **Hold angles**: one or two members stay in cover aiming at the door or corridor the player left through.
- Search sweep over nearby AAS areas the player could have reached (travel time from last known position), then a
  heightened-alert return (query state, faster reaction) instead of forgetting.

**Implemented (Phase 4)** (builds warning-free and loads/quits cleanly on escape2; **not play-tested in a fight yet**). Gated
by `cod_optTactics` (`bg_cod.enable && aiTactics`) plus `cod_aiHunt`; with either off the old vanilla hand-over to
`AIFunc_BattleChase` runs unchanged. It stays inside `AIFunc_CodCombat` (no new `AIFunc_*`, no `cast_state_t` field); the
state is in `ai_cast_cod_hunt.c` as static stale-checked arrays: one record per enemy (sighting track, target, phase,
hop slots, sweep points, participants) and one state per soldier.

- **Entry.** `CodEligibility` returning LOST (enemy unseen for `cod_aiMemoryTime`) calls `AICast_CodHuntThink` instead of
  the chase hand-over. A PEEK that did not see the enemy for 2.5 s drops its cover state and falls into the same LOST
  path. A dodging or retreating MOVE finishes first. Squad membership is unchanged (hunters still run `AIFunc_CodCombat`
  with an enemy), so squads keep regrouping. Any soldier of the tactical combat that sees the enemy feeds the track
  (`AICast_CodHuntTrack`: position, velocity); a sighting ends the hunt, and the next loss starts a new one from it.
- **Target.** Last seen position + last velocity x time since (capped at 3 s) clamped to `cod_aiHuntPredict` u, stopped
  by a hull trace, dropped to the floor (`AICast_CodDropToFloor`, exported from the cover file) and checked for an AAS area.
  An enemy only heard (no sighting) uses the vanilla `visible_pos`; no position or area at all: vanilla chase.
- **HUNT phase** (leapfrog). Soldiers start in HOLD (staggered 0.4-0.9 s + 350 ms per entity mod 4). A soldier whose
  hold time (`cod_aiHoldTime`, +-25 %) is over asks for a hop slot: at most 1 mover (2 with 4+ hunters) and always at least
  one holder; the one that has waited longest goes first. A hop goes to a `COVER_ADVANCE` spot against the target when
  the target is more than 320 u away and one exists (claimed in the cover table, travel-time based timeout), else it runs
  along the AAS route to the target for 4.5 s (7 s when close), which still leapfrogs by time. Cover searches use the
  existing `AICast_CodCoverSearchAllowed` ration; the route/vis queries share a 2-per-frame budget. The phase ends when a
  hop gets within 135 u of the target, or after `cod_aiHuntTime`.
- **Hold angles.** A holder does not fire; it stands (crouches behind LOW cover) and aims at the first point on the AAS
  route from the target that it can see (`trap_AAS_GetRouteFirstVisPos`: the door, corridor mouth or corner the player
  would come out of), odd-numbered entities alternate with the last seen point. Re-aimed about twice a second. Reaction
  time is halved while hunting (`AICast_CodAlertActive`, hook in `AICast_EntityVisible`), so a holder shoots as soon as
  the vision code reports the player and the soldier is back in the normal combat that same think.
- **Corner clearing.** While hopping the view stays on the same route-first-visible point (the corner edge), independent
  of the movement direction (strafing look), and within 190 u of it, or 170 u of the target, the soldier slows to 0.55 and
  crouch-walks (`cs->attackcrouch_time`, honoured through `AICast_CodWantsCrouch`; only characters with `ATTACK_CROUCH`).
- **SWEEP phase.** At the end of the hunt phase up to `min(hunters + 1, 5)` points are chosen: ring points around the
  sighting (4 radii up to `cod_aiSearchRadius`, 10 bearings), dropped to the floor, kept when the AAS travel time from the
  sighting's area is positive and below `0.4 * cod_aiSearchRadius` (1/100 s), taken nearest first and at least 200 u
  apart. Each soldier walks (0.8 speed) to the nearest point nobody else claimed, looks around for 2-3 s, then takes the
  next one; an unreachable or stuck point counts as visited. With nothing left it keeps looking around. After
  `cod_aiSweepTime` it is over.
- **Heightened alert.** `enemyNum` and `lastEnemy` are cleared (so the vanilla idle does not re-chase after 5 s) and the
  soldier goes to `AIFunc_DefaultStart`, whose idle drops the aiState to ALERT (vanilla alert/query rules, full field of
  view once the enemy was seen); reaction time is halved for `cod_aiAlertTime`. A sighting returns to the normal
  combat through the vanilla scan.
- **Exits.** Contact at any time; sweep timeout -> alert; a lone soldier with 3 path failures -> the vanilla chase with its
  usual 3 s back-off, after which it goes to alert (the finished hunt is remembered for 15 s). No ping-pong with vanilla
  otherwise: the hunt never hands over except on those paths.
- **Barks.** `COD_BARK_ORDERS` when a hunt and when a sweep starts, `COD_BARK_ATTACK` when a hop starts with 2+ hunters, all
  through `AICast_CodSquadBark` (squad / solo rate limit `cod_aiBarkMs`).
- **Debug** (`cod_aiDebug 1`): `HUNT start: last seen x ms ago, target ...`, `HUNT hop -> cover|target`, `HOP end (...)`,
  `HOP CLEAR corner`, `HOLD angle -> corridor|last seen point|target`, `SEARCH sweep starts`, `SEARCH area n/m ...`, `ALERT hunt
  over`, `HUNT over: contact again`, `PEEK lost the enemy: hunt`; prefixed `[ai] <name> sqN/<MODE>`.

**Files:** `ai_cast_cod_hunt.c` (new, in the Makefile `Q3GOBJ_` list), `ai_cast_cod.c` (LOST / PEEK-lost entry, track and leave
calls, crouch hook), `ai_cast_cod.h`, `ai_cast_cod_cover.c` (`AICast_CodDropToFloor` wrapper), `ai_cast_fight.c` (one gated
reaction-time hook in `AICast_EntityVisible`, `// codmod:`), `ai_cast.h`, `bg_cod.h/.c`, `mod/codmod/codmod_tuning.cfg`.

| Cvar | Default | Meaning |
| --- | --- | --- |
| `cod_aiHunt` | 1 | Hunt after losing the enemy (0 = the old vanilla chase hand-over) |
| `cod_aiHuntTime` | 30000 | Ms of hopping toward the target before the sweep starts anyway |
| `cod_aiSweepTime` | 20000 | Ms of sweeping before the soldiers go to heightened alert |
| `cod_aiSearchRadius` | 700 | U; sweep points lie in areas reachable within about this far of the sighting |
| `cod_aiHuntPredict` | 256 | U; maximum distance of the predicted position from the last sighting |
| `cod_aiHoldTime` | 3500 | Ms a soldier holds an angle before it may take its own hop |
| `cod_aiAlertTime` | 20000 | Ms of halved reaction time after the sweep found nothing |

**Deviations / risks:** "approach wide" is not implemented as a separate arc: the path is the AAS route, the soldier only
looks at the corner and slows down / crouches close to it; the sweep points come from ring samples, not from a full
walk of the AAS area graph, and are not filtered by "hidden from the target"; hunters outside any squad are handled the
same way (a squad is not required, only a shared enemy); the alert state is the vanilla ALERT reached through idle, not
the QUERY state (QUERY needs an animation and a sighting timer of its own); the reaction-time hook also applies to
hunters that are still hopping. Untested: how it plays in a real fight (hold angles that stare at a wall, hops that
run past the player's line of sight, sweeps that leave soldiers standing in the open), AAS cost with many hunters, and
savegame load in the middle of a hunt (the arrays are stale-checked like the earlier phases, but this is unverified).

### Phase 5 – Movement and aim polish

- Backpedal while firing when the player charges (`firing_bk_*`), crouch-walk between low covers, short jinks
  under fire, kick when the player is in melee range (`kick` anim, existing kick damage).
- Accuracy model: first shots of an engagement go wide (warning), accuracy grows with time in sight, drops when the
  player sprints/slides or the AI is moving or suppressed. Scaled by skill.
- Campers (`CAMPER` attribute): crouch-peek in place.
- Optional: fake lean for AIs (torso roll in cgame driven by a small entityState field) if the step-out peek looks
  too stiff. Optional: new voice lines ("Granate!", "Flankieren!").

**Implemented (Phase 5)** (builds warning-free and loads/quits cleanly on escape2; **not play-tested in a fight at all**).
New file `ai_cast_cod_polish.c` (static `polish_t` records, stale-checked, nothing in `cast_state_t`), hooked from
`ai_cast_cod.c`. Gated by `bg_cod.enable && aiTactics && cod_aiPolish` plus one switch per feature; `cod_optTactics 0`
leaves vanilla untouched.

| cvar | default | meaning |
|---|---|---|
| `cod_aiPolish` | 1 | master switch for all Phase 5 features |
| `cod_aiBackpedal` / `cod_aiBackpedalSpeed` | 1 / 150 | back away while firing when the enemy closes fast within ~400 u (AAS + ledge checked) |
| `cod_aiCrouchWalk` | 1 | crouch-walk low cover to low cover (< ~300 u, route mostly hidden), via `attackcrouch_time` |
| `cod_aiJink` | 1 | 0.3-0.6 s sideways direction changes when hit or suppressed (OPEN strafe legs, MOVE walking legs) |
| `cod_aiKick` / `cod_aiKickDamage` / `cod_aiKickCooldown` | 1 / 15 / 2500 | melee kick at ~64 u, `MOD_KICKED`, not in scripted states |
| `cod_aiAccuracy` / `cod_aiWarmup` / `cod_aiWarmupAcc` | 1 / 800 / 0.4 | first-shots warm-up, growth with time in sight, drop for sprint/slide target and moving shooter, scaled by `g_gameskill`, clamped; 1.0 for non-tactical AI |
| `cod_aiCamper` | 1 | CAMPER soldiers hold a post |

Behaviour: backpedal and jink act in OPEN/PEEK/MOVE of `AIFunc_CodCombat`; the kick runs before the grenade check and
is skipped while dodging. Campers get a fake LOW cover at their remembered anchor, so the normal MOVE/HIDE/PEEK cycle
makes them crouch-peek in place; the third compromise within 8 s drives them to ordinary cover (new anchor on
arrival). Campers are excluded from squads, pushes, hunts and chases (a lost enemy hands over to vanilla).
Deviations: no fake lean and no new voice lines (future work); only characters whose animation set has `kick` kick;
`BG_COD_MAX_CVARS` raised to 288.
Untested: everything. Check on escape2: charge a soldier (backpedal), get to ~64 u (kick), first shots miss, sprint or
slide under fire (accuracy drops, jinks), crouch-walk between low covers, find a camper (stays crouched at its post).

### Phase 6 – Difficulty, performance, regression

- Scale tokens, reaction times, peek lengths and flanking frequency by `g_gameskill`.
- Profile traces per frame with many AIs (cvar counter in the debug line); keep the budget.
- Full-campaign regression: every map's scripted sequences, friendly AIs (partisans, village), MG42 gunners,
  snipers, bosses untouched, save/load mid-fight, `cod_optTactics 0` A/B.
- Final docs (`docs/ai-tactics.md`) and tuning values.

**Implemented (Phase 6)** (builds warning-free; every SP map loads and quits cleanly; a scripted fight on escape2 incl.
save/load mid-fight ran without errors; not play-tested by a human). Overview and the full cvar table: [ai-tactics.md](ai-tactics.md).

- **Difficulty.** One table `codSkillTable` / `AICast_CodSkill( COD_SK_* )` in `ai_cast_cod.c` (easy / medium / hard):
  reaction time x1.35 / 1 / 0.75 (hook in `AICast_EntityVisible`, tactical soldier types only, `// codmod:`), peek burst
  x0.8 / 1 / 1.25, hide time x1.3 / 1 / 0.8, flank hold x1.6 / 1 / 0.7, push no-shot time x1.5 / 1 / 0.75, grenade hold and
  cooldown x1.5 / 1 / 0.75, accuracy warm-up x1.4 / 1 / 0.7 (Phase 5, now from the same table), hunt / sweep / alert
  durations x0.7 / 1 / 1.3. Attack tokens stay 2 / 3 / 4. `cod_aiSkillScale` (default 1) switches all factors to 1.0.
- **Performance counters.** `ai_cast_cod.h` wraps `trap_Trace`, `trap_AAS_AreaTravelTimeToGoalArea` and
  `trap_AAS_GetRouteFirstVisPos` in the tactical files with counting macros; cover searches are counted in the ration.
  `cod_aiDebug 2` prints `[ai] perf: ...` once per second. Measured on escape2 (nazi1-3 in a real fight, god mode, skill
  easy and hard): 10 tactical frames/s; mean traces per frame about 2.5, a cover search costs 150-480 traces in its frame
  (one search per frame at most); AAS queries at most 7 per frame, usually 0; at most 2-3 soldiers in combat at a time.
  No hot spot found that justified a behaviour-neutral change (the per-think strafe check is 3 traces), so no code was
  changed for performance. A big fight (6+ soldiers) was not reachable in the automated runs.
- **Regression (automated).** All 32 SP maps (including cutscenes) loaded with tactics on and quit via `+quit`, no
  ai/cast/script/AAS errors; `cod_optTactics 0` on escape2 loads, nothing tactical runs; `savegame` / `loadgame` in the
  middle of a three-soldier fight worked and the fight continued after the load.

Human checklist: scripted sequences (cell guard, cutscene soldiers, `gotomarker` patrols) unchanged; friendly AIs (partisans,
village); MG42 gunners and snipers keep their posts; bosses and monsters unchanged; flank / push / grenade / hunt behaviour
in a real 4+ soldier fight on each skill; backpedal, kick, jinks, campers; mid-fight save/load while hunting or dodging a
grenade; `cod_optTactics 0` A/B in the menu.

## 5. Implementation process

Each phase is implemented by a Sonnet subagent from the spec above, then reviewed (diff read, build, smoke run) by
the main agent before the user's in-game check. Engine/game code changes are committed in the `iortcw/` submodule
and pushed to the fork, then the outer repo bumps the pointer, only when the user asks.
