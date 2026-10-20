# Tactical enemy AI

Human enemy soldiers in the remaster fight like a squad instead of standing in the open: they take cover, peek, strafe,
share what they see, take turns shooting, flank, push for an angle, throw grenades, react to being shot at, and search
methodically when they lose you. Monsters, bosses, civilians, friendly characters, scripted sequences and MG42
gunners keep the original behaviour. Design history and per-phase deviations are in
[ai-overhaul-plan.md](ai-overhaul-plan.md); this page is the overview of the finished system.

Source: `iortcw/SP/code/game/` (submodule). `ai_cast_cod.c` combat state machine, `ai_cast_cod_cover.c` cover finder,
`ai_cast_cod_squad.c` squads / tokens / flank / push, `ai_cast_cod_hunt.c` search and hunt, `ai_cast_cod_polish.c`
movement and aim polish, `bg_cod.c` the cvar table.

## Turning it on and off

| Switch | Where | Effect |
| --- | --- | --- |
| `cod_optTactics` | MODS > GAMEPLAY > "Tactical Enemies" (archived, user-facing) | 0: every soldier runs the vanilla AI, bit for bit. 1: tactical AI. |
| `cod_aiTactics` | `codmod_tuning.cfg` (internal master) | Set from `cod_optTactics` at startup; leave at 1. |
| `cod_aiSquad` | tuning | Squad layer (tokens, fire and move, flanking, suppression, callouts). Off: soldiers act alone. |
| `cod_aiPush` | tuning | Pushing for an angle against a player who hides behind cover. |
| `cod_aiHunt` | tuning | Hunting / sweeping after losing you. Off: the old vanilla chase. |
| `cod_aiPolish` | tuning | Master for the Phase 5 polish; each of `cod_aiBackpedal`, `cod_aiCrouchWalk`, `cod_aiJink`, `cod_aiKick`, `cod_aiAccuracy`, `cod_aiCamper` is a separate switch. |
| `cod_aiOpportunity`, `cod_aiMorale` | tuning | Reaction to a reloading / sliding player; squad morale break. |
| `cod_aiSkillScale` | tuning | 1: difficulty scaling by `g_gameskill`. 0: medium values everywhere (and token count stays by skill, see below). |

All of it is gated on `bg_cod.enable && bg_cod.aiTactics`. A soldier is handled by the tactical code only if it is a
human soldier type (soldier, American, elite guard, black guard, partisan, frogman), has a usable bullet weapon, is not
on an MG42, follows no leader, no level script is controlling it (`gotomarker`, `noattack`, `nosight`, `denyactivate`,
...), and it saw the enemy within `cod_aiMemoryTime`. Anything else falls through to the vanilla function untouched.

## What soldiers do, by phase

1. **Cover and fighting from cover.** A soldier that sees you samples its surroundings for cover (walls, crates,
   doorframes), runs to it (sprinting when far), crouches behind low cover or hugs the corner, and then peeks: stands
   up or steps out, fires a burst, ducks back. Caught in the open it strafes while shooting. It reloads out of sight,
   and re-searches when the spot is compromised or you moved a lot.
2. **Squads.** Soldiers fighting the same enemy near each other form a squad that shares the last known position. Only
   a few may shoot at once (attack tokens), the rest hide, reposition or flank. Fire and move: one soldier at a time
   advances cover to cover while others fire. If you hold one spot for a while a flanker circles to another bearing.
   While a teammate moves the others fire suppressively at your last position. Callouts are rate limited.
3. **Pushing for an angle (2b).** If nobody gets a real shot at you (you are prone behind a table), a soldier moves to a
   spot with a clear line to your body, else throws a grenade, else advances.
4. **Threat reactions.** Grenades thrown at a player who camps or hides behind a corner; defensive handling of
   incoming grenades (kick back, run to cover out of the blast, dive); near misses suppress soldiers (they hide
   longer, shoot worse); being hit in the open or at low health sends them to cover or a retreat spot; a squad that lost
   half its members falls back; a reloading, sliding or prone player is attacked at once.
5. **Search and hunt.** Without contact the squad leapfrogs to the predicted position, holders cover the corridor you
   left through, corners are cleared at a crouch-walk, then points around the sighting are swept, and finally the
   soldiers stay on heightened alert (half reaction time) for a while.
6. **Movement and aim polish.** Backing away when you charge, crouch-walking between low covers, short sideways jinks
   when hit, a kick in melee range, an accuracy model (first shots go wide and improve with time in sight, worse
   against a sprinting or sliding target and from a moving shooter), campers crouch-peek at their post.
7. **Difficulty and performance.** See below.

## Difficulty (`g_gameskill`)

One table in `ai_cast_cod.c` (`codSkillTable`, accessor `AICast_CodSkill`). Time factors multiply a duration, so above 1
means slower / longer. All factors are 1.0 with `cod_aiSkillScale 0`.

| What | Easy | Medium | Hard | Cvar it scales |
| --- | --- | --- | --- | --- |
| Attack tokens (shooters per squad) | 2 | 3 | 4 | `cod_aiAttackTokens` 0 = auto (a non-zero value overrides) |
| Reaction time (soldier types only) | x1.35 | x1.0 | x0.75 | attribute `REACTION_TIME` |
| Peek burst length | x0.80 | x1.0 | x1.25 | `cod_aiPeekMin/Max` |
| Hide time between peeks | x1.30 | x1.0 | x0.80 | `cod_aiHideMin/Max` |
| Flank hold (player holds a spot) | x1.60 | x1.0 | x0.70 | `cod_aiFlankHold` |
| Push no-shot time | x1.50 | x1.0 | x0.75 | `cod_aiNoShotTime` |
| Grenade hold / cooldown | x1.50 | x1.0 | x0.75 | `cod_aiGrenadeHold`, `cod_aiGrenadeCooldown` |
| Accuracy warm-up | x1.40 | x1.0 | x0.70 | `cod_aiWarmup` |
| Hunt, sweep and alert durations | x0.70 | x1.0 | x1.30 | `cod_aiHuntTime`, `cod_aiSweepTime`, `cod_aiAlertTime` |

`g_gameskill` is 0 easy, 1 medium, 2 hard. The token count is the only value not behind `cod_aiSkillScale`.

## Cvar reference

Generated from `bg_codCvars[]` (`bg_cod.c`), the field comments in `bg_cod.h` and `mod/codmod/codmod_tuning.cfg` (the
effective defaults; the code defaults are the same). Times are ms, distances are game units (u), AAS travel time is in
1/100 s. These are internal tuning values (not archived): edit `codmod_tuning.cfg`, or `set` them in the console.
`cod_aiSpeed*` and `cod_aiSprint*` belong to the older movement-speed work and are in the gameplay docs.

| Cvar | Default | Meaning |
| --- | --- | --- |
| `cod_aiTactics` | 1 | internal master switch of the whole tactical AI; `cod_optTactics 0` clears it |
| `cod_aiDebug` | 0 | 1 = console line per tactical state change, 2 = also draw cover/peek spots and print the once-per-second `[ai] perf:` line |
| `cod_aiMemoryTime` | 4000 | ms the enemy counts as "recently seen" for tactical eligibility |
| `cod_aiCoverRadius` | 768 | u, how far the cover finder looks around the AI |
| `cod_aiCoverMaxTravel` | 300 | AAS travel time (1/100 s) cap for a cover spot |
| `cod_aiCoverSearchesPerFrame` | 1 | cover searches allowed per server frame (global ration) |
| `cod_aiPeekMin` | 1000 | ms, shortest peek burst |
| `cod_aiPeekMax` | 2500 | ms, longest peek burst |
| `cod_aiHideMin` | 600 | ms, shortest stay behind cover |
| `cod_aiHideMax` | 1800 | ms, longest stay behind cover |
| `cod_aiStrafeMin` | 600 | ms, shortest open-ground strafe leg |
| `cod_aiStrafeMax` | 1400 | ms, longest open-ground strafe leg |
| `cod_aiSquad` | 1 | squad tactics switch (tokens, fire and move, flanking, suppression) |
| `cod_aiAttackTokens` | 0 | soldiers allowed to shoot at once per squad; 0 = by skill (2/3/4) |
| `cod_aiTokenTime` | 3500 | ms, longest continuous token hold when others are waiting |
| `cod_aiSquadRange` | 1200 | u, max distance between squad members |
| `cod_aiFlankHold` | 6000 | ms the player must hold one spot before a flanker is sent |
| `cod_aiFlankMove` | 128 | u, the player counts as holding while he stays within this of the anchor |
| `cod_aiAdvanceMinDist` | 400 | u, only advance (bounding overwatch) while the threat is farther than this |
| `cod_aiSuppressMs` | 1500 | ms of suppressive fire when a teammate starts moving |
| `cod_aiBarkMs` | 5000 | ms between callouts per squad |
| `cod_aiPush` | 1 | Phase 2b: push for an angle when the player sits behind cover nobody can hit |
| `cod_aiNoShotTime` | 4000 | ms of trying without a real shot before a soldier / squad pushes |
| `cod_aiPushCooldown` | 9000 | ms between pushes per squad (or soldier) |
| `cod_aiGrenadeHold` | 4000 | Phase 3: ms the player must stay behind the same cover before a grenade; 0 = vanilla flush rules |
| `cod_aiGrenadeCooldown` | 8000 | Phase 3: ms between grenade throws per squad (or soldier) |
| `cod_aiSuppressDecay` | 0.35 | Phase 3: suppression lost per second |
| `cod_aiSuppressThreshold` | 0.5 | Phase 3: suppression value (0..1) from which a soldier counts as suppressed |
| `cod_aiRetreatHealth` | 35 | Phase 3: percent of max health below which a hit soldier retreats |
| `cod_aiOpportunity` | 1 | Phase 3: push / peek at once while the player reloads, switches weapons, slides or goes prone |
| `cod_aiMorale` | 1 | Phase 3: a squad that lost half its members falls back |
| `cod_aiHunt` | 1 | Phase 4: a soldier that lost the enemy hunts (hops, holds angles, sweeps) instead of the vanilla chase |
| `cod_aiHuntTime` | 30000 | Phase 4: ms of hunting toward the predicted position before the sweep starts anyway |
| `cod_aiSweepTime` | 20000 | Phase 4: ms of searching nearby areas before the soldiers go to heightened alert |
| `cod_aiSearchRadius` | 700 | Phase 4: u; sweep points are areas the player could have reached within about this far |
| `cod_aiHuntPredict` | 256 | Phase 4: u; the predicted position is at most this far from where the player was last seen |
| `cod_aiHoldTime` | 3500 | Phase 4: ms a soldier holds an angle before it may take its own hop |
| `cod_aiAlertTime` | 20000 | Phase 4: ms of heightened alert (half the reaction time) after the search found nothing |
| `cod_aiPolish` | 1 | Phase 5: master switch of the movement / aim polish below |
| `cod_aiBackpedal` | 1 | Phase 5: back away while firing when the player charges |
| `cod_aiCrouchWalk` | 1 | Phase 5: crouch-walk between low covers when the route stays hidden |
| `cod_aiJink` | 1 | Phase 5: short sideways direction changes under fire |
| `cod_aiKick` | 1 | Phase 5: kick the player in melee range |
| `cod_aiAccuracy` | 1 | Phase 5: warm-up / moving-target / moving-shooter accuracy model |
| `cod_aiCamper` | 1 | Phase 5: CAMPER soldiers crouch-peek in place instead of vanilla behaviour |
| `cod_aiBackpedalSpeed` | 150 | Phase 5: u/s, closing speed of the player from which a soldier backs away |
| `cod_aiKickDamage` | 15 | Phase 5: damage of a soldier's kick |
| `cod_aiKickCooldown` | 2500 | Phase 5: ms between kicks per soldier |
| `cod_aiWarmup` | 800 | Phase 5: ms of sight until a soldier reaches full accuracy (scaled by skill) |
| `cod_aiSkillScale` | 1 | Phase 6: 1 = scale timings by g_gameskill (easy slower/forgiving, hard sharper), 0 = off |
| `cod_aiWarmupAcc` | 0.4 | Phase 5: accuracy multiplier at first sight (0.4 = first shots go wide) |

## Debug

- `cod_aiDebug 1`: one console line per state change, all rate limited. Format
  `[ai] <aiName> sq<id>/<ROLE> <detail>`. `sq0` / `SOLO` = no squad; ROLE is SOLO, FIRE, COVER, MOVE, FLANK or PUSH, or
  HUNT / HOLD / HOP / SWEEP in the search code. Typical lines: `vanilla->tactics` (the soldier is now tactical),
  `OPEN->MOVE cover=LOW d=312 ...` (sub-state change; OPEN / MOVE / HIDE / PEEK), `token granted|denied|rotated out`,
  `FLANK ordered / starts moving / in position`, `PUSH no shot for N ms -> angle spot`, `GRENADE ...`, `DODGE ...`,
  `SUPPRESSED v=`, `RETREAT ...`, `MORALE broken`, `HUNT start ... / HOLD angle / HOP / SEARCH area n/m / ALERT hunt over`,
  `ACC warmup start xN over N ms (skill N)`, `KICK ...`, `tactics->vanilla (enemy not seen for N ms)`.
- `cod_aiDebug 2`: also draws the chosen cover and peek spot (box on the floor and a pole to eye height), and prints once
  per second `[ai] perf: N tactical frames/s, traces avg A max M, aas avg A max M, cover searches S, soldiers avg A max M`.
  A "tactical frame" is a server frame in which at least one soldier ran the tactical combat. Traces count every
  `trap_Trace` made by the tactical code (not the vanilla AI, not `AICast_PredictMovement`), "aas" counts AAS route
  queries, a cover search (up to ~480 traces, rationed by `cod_aiCoverSearchesPerFrame`) shows up as the max.

## Performance

Cost is dominated by cover searches (a few hundred hull / line traces each), rationed to one per server frame
(urgent ones, e.g. after a hit, bypass the ration). Everything else is a handful of traces per soldier think. Hunt route
and visibility queries share a 2-per-frame budget. See the numbers in the Phase 6 note of the plan.

## Known limitations

- No lean or blind-fire animations exist for the soldier models; peeking is a step-out or a stand-up.
- No new voice lines ("Granate!", "Flankieren!"); only the existing ORDERS / ATTACK scripts are used as callouts.
- Scripted moments (a soldier under `gotomarker`, `noattack`, ...), MG42 gunners, snipers, zombies, bosses and friendly
  partisans use the vanilla code by design.
- Sweep points come from ring samples, not a walk of the AAS area graph; "approach wide" is only a look-and-slow-down.
- A hunter that cannot see you while a squad mate still fights you can restart its hunt every hold (seen in a debug run
  with two soldiers; harmless, it just keeps holding its angle).
- State lives in static arrays, not in `cast_state_t`: a savegame load resets all tactical state, soldiers re-evaluate
  on their next think.
- The bulk of the behaviour was verified by loading every map and short scripted fights, not by a full campaign
  playthrough. See the checklist in the Phase 6 note of the plan for what still needs a human.
