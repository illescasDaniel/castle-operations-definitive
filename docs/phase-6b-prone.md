# Phase 6b — Prone (ported from Enemy Territory)

**Prerequisite:** Phase 6 (slide) confirmed. Prone touches the same stance code as crouch smoothing (phase 2),
ADS (phase 3) and slide (phase 4), so it goes last.
**Read first:** [architecture.md](architecture.md). Prone state must be networked and time-based
(golden rules 2 & 3), and never apply to AI (rule 1).

RTCW SP has no prone. Enemy Territory (ET) has one, and both its **code** and its **animations**
are available to us:

| Source | What | Where | Use |
|---|---|---|---|
| **ET: Legacy** (primary) | Maintained, bug-fixed fork of the ET GPL code: `PM_CheckProne`, legs **and head** prone boxes, entry "nudge" so prone fits near walls, view limits | `github.com/etlegacy/etlegacy` pinned at `626020f` (v2.86.1). `src/game/bg_pmove.c` `PM_CheckProne` ~L890-1105, `PM_TraceLegs`/`PM_TraceHead`/`PM_TraceAllParts` ~L265-491, view limits ~L4650-4730. `src/game/bg_misc.c` box sizes ~L84-88, `BG_Legs/HeadCollisionBoxOffset` ~L4950-4993 | Reference for tier A. GPLv3 like ioRTCW, so porting with an attribution comment is fine |
| ET GPL source (original) | The same code before Legacy's fixes. Easier to read, closer to RTCW's code style | `github.com/id-Software/Enemy-Territory` (`40342a9`), `src/game/bg_pmove.c` ~L320-400, ~L867-1012, ~L4878-4975; `src/cgame/cg_view.c` ~L715 (`PRONE_TIME 500`); `src/cgame/cg_weapons.c` ~L1893 (crawl gun tilt) | Secondary. Use it to see the minimal version of each piece |
| ET game data (user owns it) | Prone body animations | `…/Wolfenstein Enemy Territory/etmain/pak0.pk3` → `animations/human/base/body.mdx`, `body.aninc`, `animations/scripts/human_base.script` | Optional tier B (cosmetic third-person) |

## Tiers

| Tier | What | Value in SP | Effort | Gate |
|---|---|---|---|---|
| **A — Prone gameplay** | Stance, bbox, view height, speed, transitions, fire/ADS rules, view limits, viewmodel tilt, headshot box | **High.** This is what the player feels | M–L | User confirms prone feel |
| **B — Third-person prone animations** | Retarget ET prone anims onto RTCW's `bj2` model and add prone move types to the anim script | **Low.** The player's own body is only seen in `cg_thirdPerson`, mirrors and some cutscenes | L (tool + spike) | Separate. Only if the user asks after tier A |
| C — AI prone | AI going prone | None. AI scripts and anims don't know about it | — | **Not planned** |

Without tier B, the third-person body plays the **crouch** animations while prone. That is the only
visible flaw, and it is cosmetic.

---

## Tier A — Prone gameplay

### Behaviour spec (CoD4 feel)

| | |
|---|---|
| **Enter** | Press `+prone` (toggle, `CTRL`) while on the ground, not on a ladder, `waterlevel < 2`, not on an MG42, not sliding, not in a transition or cooldown, and the prone box fits (trace) |
| **Going down** | Bbox and view height switch at once. The camera eases down over `cod_proneDownTime` (350 ms). No movement, firing or ADS until it ends |
| **While prone** | Crawl at `run × cod_proneScale` (30 u/s). No sprint, no lean, no jump. Firing allowed while still. While crawling the gun tilts away and can't fire (`cod_proneCrawlFire 0`). ADS allowed while still. Crawling eases ADS out. Pitch clamped to `cod_pronePitchUp/Down` (40°/40°). Lower spread (`cod_proneSpreadScale 0.5`). No footsteps, slow bob |
| **Exit** | `+prone` again, jump, or crouch press. Needs room (trace): stand if the standing box fits, else crouch if crouch fits, else stay prone. Holding crouch makes it end in crouch. The camera eases up over `cod_proneUpTime` (350 ms) with movement/fire locked |
| **Forced exit** | Leaving the ground (pushed off a ledge), `waterlevel >= 2`, death, respawn, `cod_proneEnable 0`. Use the same room rules. If neither fits, ducked |
| **Cooldown** | `cod_proneCooldown` (400 ms) after any transition ends, so toggle spam can't flicker the stance |

The brief asked for prone transitions ~30% faster than the base game. RTCW has none, so the base is
ET's `PRONE_TIME 500` → 350 ms.

### State (all networked)

| Field | Meaning |
|---|---|
| `stats[STAT_COD_FLAGS] & COD_SF_PRONE` | In the prone stance (bbox and view height are prone) |
| `stats[STAT_COD_FLAGS] & COD_SF_PRONE_MOVING` | Crawling. Hysteresis from ET: on above 40 u/s with input, off below 20 u/s without input. Drives the gun tilt and the fire block |
| `stats[STAT_COD_FLAGS] & COD_SF_PRONE_HELD` | Latch of last frame's `+prone`, for prediction-safe press-edge detection (don't use `pm->oldcmd`) |
| `stats[STAT_COD_FLAGS] & COD_SF_CROUCH_HELD` | Same latch for crouch (`cmd.upmove < 0`), so a crouch held from before going prone doesn't immediately exit. Jump uses vanilla's `PMF_JUMP_HELD` |
| `stats[STAT_COD_STANCE]` (new, `stats[12]`) | `> 0`: ms left in a prone transition (down if `COD_SF_PRONE` is set, up if not). `< 0`: cooldown ms (counts up to 0). `0`: idle |
| `ps->viewheight` | Already networked. Set to `cod_proneViewHeight` (−8) while prone |
| `pm_flags & PMF_DUCKED` | **Also set while prone**, as ET does. Every vanilla "is low" check (AI hearing, `EF_CROUCHING`, crouch anims, crouch spread) keeps working |

Why not ET's layout: ET uses `eFlags` bits (`EF_PRONE 0x00080000`), but in RTCW that value is
`EF_TAGCONNECT`, and RTCW SP has only `0x80000000` free. ET also keeps `proneTime` in the
non-networked `pmoveExt_t`. That caused prediction errors: ET: Legacy had to add a client-side ring
buffer of `pmoveExt_t` per command (`cgame/cg_predict.c` `oldpmext[]`) to fix them. We use stats
instead, which are networked, need no engine changes, and avoid that whole problem.

### Input

```
// mod/codmod/codmod.cfg (every launch)
alias +prone "+wbutton7"
alias -prone "-wbutton7"
// mod/codmod/codmod_binds.cfg (first launch only)
bind CTRL "+prone"        // CoD4 default. Vanilla CTRL is a second +attack (MOUSE1 stays fire); `c` stays crouch
```
Existing installs keep their binds. Tell the user to run `scripts/run.sh --reset-binds` once or to
bind `+prone` themselves.
`bg_public.h`: `#define WBUTTON_COD_PRONE WBUTTON_EXTRA7  // codmod: bound via +wbutton7 / +prone`.
`+wbutton7` is already registered in `client/cl_input.c:1075`. **grep first** to confirm that
`WBUTTON_EXTRA7` (128) has no game-code users. RTCW has no `doubleTap` in `usercmd_t`, so ET's
"crouch + double-tap forward" entry is **not** ported. Use the key only.

### Implementation — `bg_pmove.c` (port of ET `PM_CheckProne`)

#### A.1 `static void PM_CodCheckProne( void )`
Call it in `PmoveSingle` right **before** `PM_CheckDuck()` (both call sites, ~L4162 and ~L4187).
It runs for the player only (`!ps->aiChar && bg_cod.enable && bg_cod.proneEnable`). For AI and when
disabled, make sure `COD_SF_PRONE*` are clear and return.

1. Timer tick: `stats[STANCE] > 0` → subtract `pml.msec` (floor 0, and when it reaches 0 start the
   cooldown `-proneCooldown`). `< 0` → add `pml.msec` (cap 0).
2. Edges: `pressed = ( cmd.wbuttons & WBUTTON_COD_PRONE ) && !( flags & COD_SF_PRONE_HELD )`,
   `crouchPressed = cmd.upmove < 0 && !( flags & COD_SF_CROUCH_HELD )`,
   `jumpPressed = cmd.upmove > 0 && !( pm_flags & PMF_JUMP_HELD )`. Then update both COD latches
   (every frame, also when not prone).
3. **Enter** (not prone, `pressed`, `stats[STANCE] == 0`, conditions from the spec): set temporary
   `pm->maxs[2] = cod_proneMaxsZ` and trace `pm->trace( ..., origin, mins, maxs, origin, ... )`.
   If not `allsolid`: set `COD_SF_PRONE`, `stats[STANCE] = proneDownTime`, clear sprint/ADS/lean
   state, zero horizontal velocity (CoD4 stops you when you drop). ET reference ~L906-930.
   With `cod_proneLegs 1` (A.7), use ET: Legacy's entry instead (~L936-1030): trace the legs box and
   then the head box. If one hits, nudge the player away from the wall with `PM_StepSlideMove` and
   retry once, so going prone next to a wall works instead of failing.
4. **Exit** (prone and (`pressed` or `jumpPressed` or `crouchPressed`), and
   `stats[STANCE] == 0`), or forced exit (not on ground, `waterlevel >= 2`, `pm_type != PM_NORMAL`,
   disabled). Trace the standing box (`ps->maxs[2]`), then the crouch box (`ps->crouchMaxZ`). If either
   fits: clear `COD_SF_PRONE | COD_SF_PRONE_MOVING` and set `stats[STANCE] = proneUpTime`
   (forced exits: `0`, no lock). If the standing box fits and crouch isn't held, clear `PMF_DUCKED`;
   otherwise leave it set and the vanilla `PM_CheckDuck` takes over. If nothing fits, stay prone.
   A jump press must **not** also jump this frame: zero `cmd.upmove` after using it. ET reference ~L938-965.
5. **While prone**: update `COD_SF_PRONE_MOVING` with ET's hysteresis (~L975-995), set
   `PMF_DUCKED`, `pm->maxs[2] = cod_proneMaxsZ`, `ps->viewheight = cod_proneViewHeight`
   (ET ~L1008-1009).

#### A.2 `PM_CheckDuck` change
If `COD_SF_PRONE`: return early after A.1 has set the box and view height (otherwise it would
overwrite them with crouch values).

#### A.3 Movement
- `PM_CmdScale` (player path): if prone, `scale *= proneScale / crouchScale` because the vanilla
  ducked clamp already applies `crouchScale`. Alternatively, branch on prone before the ducked clamp
  in `PM_WalkMove` (~ the `PMF_DUCKED` speed clamp). Pick whichever is clearer after phase 2's changes.
  Expected HUD value: 30 u/s (±2%).
- During a transition (`stats[STANCE] > 0`): `cmd.forwardmove = cmd.rightmove = 0` (player only).
- `PM_CheckJump`: no jump while prone (ET ~L760). The exit in A.1 already consumes the press.
- `PM_CodUpdateSprint`: no sprint while prone or during a transition.
- `PM_UpdateLean`: no lean while prone (CoD4).
- Ladders: can't be prone on a ladder (entry check, and a forced exit if `pml.ladder`).

#### A.4 Weapons
- `PM_Weapon`: block `BUTTON_ATTACK` (treat as not pressed) while `stats[STANCE] > 0`, and while
  `COD_SF_PRONE_MOVING` unless `cod_proneCrawlFire 1` (ET ~L3555). Reload and weapon switch stay allowed.
- `BG_CodCanADS` (phase 3): false during a transition, and while crawling unless `cod_proneCrawlADS 1`.
- Spread (`g_weapon.c`, same place as the ADS multiplier from phase 3): `× cod_proneSpreadScale` when
  prone and not crawling. It stacks with ADS.
- Flamethrower, Venom and Tesla: allowed while still. Panzerfaust: blocked while prone (`cod_pronePanzer 0`);
  check RTCW's `WP_PANZERFAUST` fire path. Throwing grenades: allowed (CoD4).
- MG42 can't be mounted while prone. RTCW mounts via `+activate` on the MG42 entity: add a prone
  check in the mount code (`g_active.c` / `g_misc.c` `mg42` use). **grep** `EF_MG42_ACTIVE` setters.

#### A.5 View limits — `PM_UpdateViewAngles` (`bg_pmove.c:3684`)
Its signature has no `pm`, but it gets `ps` and `cmd`. After the vanilla angle computation, if prone
and `!ps->aiChar`: clamp `viewangles[PITCH]` to `[-pronePitchUp, +pronePitchDown]` and fix
`delta_angles[PITCH] = ANGLE2SHORT( clamped ) - cmd->angles[PITCH]`, as ET does (~L4860-4876).
**No yaw limit** in tier A. ET only undoes a yaw if the legs box would rotate into a wall (A.7).

#### A.6 Feet & bob
`PM_Footsteps`: when prone, no footstep events. Advance `bobCycle` at `cod_proneBob` (0.2) of the
crouch rate (ET ~L2136). The legs anim keeps the crouch move types until tier B.

#### A.7 (optional, off by default) Legs and head boxes — `cod_proneLegs 0`
ET adds a legs box 32 u behind the origin along the yaw (`playerlegsProneMins {-13.5,-13.5,-24}`,
`Maxs {13.5,13.5,-14.4}`). ET: Legacy also adds a head box 24 u in front
(`playerHeadProneMins {-6,-6,-12}`, `Maxs {6,6,0}`). Both are traced in `PM_TraceAllParts` (used by
`bg_slidemove.c` and the ground trace), on entry/exit, and on yaw changes. In first person nobody
sees legs inside walls, so tier A ships **without** them. Port ET: Legacy's `PM_TraceLegs` /
`PM_TraceHead` / `PM_TraceAllParts` / `PM_TraceAll` and `BG_Legs/HeadCollisionBoxOffset`, and
switch `bg_slidemove.c`'s `pm->trace` calls to `PM_TraceAll`, only if:
- tier B is done and the clipping looks bad in third person, or
- the player can crawl backwards into geometry and get stuck.

### Implementation — `game`

- **Headshots** (`g_combat.c:715-731`, `IsHeadShot`): the player branch uses `PMF_DUCKED` →
  `crouchViewHeight + 8`, which is wrong while prone. Add a prone branch first: head at
  `origin + ( 0, 0, cod_proneViewHeight + 4 )` pushed ~16 u forward along the yaw. To verify, add
  a temporary `cod_debugHead 1` that prints the head box origin and each hit's `IsHeadShot` result.
- **Death / spawn / map change**: clear `COD_SF_PRONE*` and `STAT_COD_STANCE` in `ClientSpawn` and
  on death (pmove's `PM_DEAD` path, as ET does at ~L5528/~L5593).
- **AI**: nothing to change. AI sight already uses the eye position, so prone behind low cover is
  naturally stealthier. Check this in testing. It's a feature, not a bug.

### Implementation — `cgame`

- **Camera** (`cg_playerstate.c:549` sets `cg.duckChange`, `cg_view.c:628` applies it): phase 2
  replaced `DUCK_TIME` with `cod_duckTime`. Extend it: when the old or the new `viewheight` equals
  `cod_proneViewHeight`, store the duration in a new `cg.codDuckDuration` (`proneDownTime` if
  going down, else `proneUpTime`) and use it instead of `cod_duckTime`, with the same ease-out.
  ET does the same with `PRONE_TIME 500` (`et cg_view.c` ~L715).
- **Viewmodel**:
  - While `COD_SF_PRONE_MOVING`, ease the gun into a "crawl" pose (pitch down ~25°, yaw ~15°, drop ~4 u)
    over 200 ms, and back out over 200 ms. ET does this at `cg_weapons.c` ~L1893-1910; track
    `cg.codProneMovingTime` from the flag edge.
  - During a transition, dip the gun (lower by ~6 u × transition fraction).
  - Put the numbers in `cod_proneGun*` cvars for tuning.
- **Crosshair**: hide while crawling (fire is blocked).
- **Debug HUD**: add `stance: stand/crouch/prone(+moving)`, `stance ms`, `viewheight`.
- **Sound** (optional): on entering prone, play an existing RTCW body-fall / landing sound
  through a predicted event (`EV_COD_PRONE`, added just before `EV_MAX_EVENTS` like phase 4's
  `EV_COD_SLIDE`). **Don't** ship ET sounds.

### Interactions

| Situation | Expected |
|---|---|
| Sprinting → `+prone` | Sprint ends, goes prone (no dive in tier A, see the slide note below) |
| Sliding → `+prone` | Ignored by default. Optional `cod_slideToProne 1`: end the slide into prone (a cheap "dive") |
| ADS → `+prone` | ADS eases out during the transition, then resumes if still held |
| Prone + `+zoom` binoculars | Allowed |
| Prone + scoped rifle (`WP_SNIPERRIFLE`, etc.) | Allowed. Classic prone sniping. Crawling exits the scope (RTCW's alt-weapon switch) or blocks fire, whichever is simpler |
| Prone + lean keys | Ignored |
| Prone + reload / switch weapons | Allowed |
| Pushed off a ledge / explosion knockback airborne | Forced exit to stand/crouch |
| Water rising (`waterlevel >= 2`) | Forced exit |
| Cutscene / camera (`EF_VIEWING_CAMERA`) | Forced exit, no transition lock |
| Save while prone → load | Loads prone (stats are saved) or, if `pm_flags` was lost, A.1 rebuilds the bbox from the flag. Never stuck in geometry |

### Defaults (`cod_*`, also in [reference-values.md](reference-values.md))

| Cvar | Default | Note |
|---|---|---|
| `cod_proneEnable` | 1 | |
| `cod_proneScale` | 0.15 | × jog 200 → **30 u/s** (CoD4 0.15. ET 0.21 → 67 u/s at ET's speed) |
| `cod_proneViewHeight` | −8 | eye 16 u above the feet (ET. CoD4 ≈ 11 × 64/60 ≈ 12) |
| `cod_proneMaxsZ` | 16 | box top, same as crouch (ET). ET: Legacy tried 12 and went back to 16 (`PRONE_BODYHEIGHT_BBOX`, "back to vanilla behaviour"), so lowering it is risky. Lower = hide behind lower cover but more chance of getting stuck when standing up |
| `cod_proneDownTime` / `cod_proneUpTime` | 350 / 350 ms | view ease plus move/fire lock (ET 500 × 0.7) |
| `cod_proneCooldown` | 400 ms | ET has a 750 ms toggle gate |
| `cod_pronePitchUp` / `cod_pronePitchDown` | 40° / 40° | ET ±40 |
| `cod_proneCrawlFire` / `cod_proneCrawlADS` | 0 / 0 | CoD4 lowers the gun while crawling |
| `cod_proneSpreadScale` | 0.5 | |
| `cod_proneBob` | 0.2 | ET |
| `cod_pronePanzer` | 0 | |
| `cod_proneLegs` | 0 | A.7 |
| `cod_slideToProne` | 0 | |

### Test plan (tier A)

| # | Scenario | Expected |
|---|---|---|
| 1 | `CTRL` on flat ground, then `CTRL` | Down in ~350 ms, up in ~350 ms, smooth camera, no pop |
| 2 | Crawl forward / back / strafe | HUD ≈ 30 u/s. No footsteps. Gun tilts while moving, can't fire |
| 3 | Still and prone: fire, ADS, reload | Fire works, ADS works, spread is visibly tighter than standing hip-fire |
| 4 | Prone under a crouch-height overhang → `CTRL` | Ends in crouch, stands when clear |
| 5 | Prone under a lower overhang (if `cod_proneMaxsZ` was lowered) | Can't get up. Stays prone. No stuck, no jitter |
| 6 | Toggle spam | Never flickers. Cooldown respected |
| 7 | Jump while prone | Stands up (no jump that frame) |
| 8 | Look up and down | Clamped at 40°/40°, no snapping, no `cg_showmiss` |
| 9 | Crawl off a ledge | Forced exit, normal fall |
| 10 | Prone on stairs / slopes | Crawls up and down stairs (step height unchanged) |
| 11 | Ladder / water / MG42 | Can't go prone on a ladder or deep water. Can't mount MG42 while prone |
| 12 | Guards in `escape1` | Prone behind low cover is harder to see. Headshots on a prone player land on the head area (log `IsHeadShot`) |
| 13 | Save prone → load | Clean. Never inside geometry |
| 14 | `com_maxfps 60` vs `250`, `cg_showmiss 1` | Same speeds and timings. No prediction errors |
| 15 | `cod_enable 0` / `cod_proneEnable 0` while prone | Forced exit, vanilla behaviour |
| 16 | AI | No AI ever goes prone. Patrols unchanged |

### Acceptance criteria (gate)
- [ ] All 16 scenarios pass.
- [ ] Report with the final defaults, then **stop**. Ask the user whether they want tier B.

---

## Tier B — Third-person prone animations (optional, cosmetic)

### Verified feasibility (2026-10-08)
- ET `animations/human/base/body.mdx`: MDXW v2, 4887 frames, 53 bones.
  `body.aninc` lists e.g. `prone_crawl` (frame 4431, 19 frames), `prone_crawl_bk`, `prone_pistol_*`,
  `prone_rifle_*`, `prone_mg_*`, plus per-weapon `prone_rifle.mdx` / `prone_pistol.mdx` / ….
- RTCW `models/players/bj2/body.mds`: MDSW v4, 776 frames, 70 bones = the **same 53 `Bip01 …`
  bones** (same names, same parents, same torso weights) + 17 `tag_*` bones (flags = 1), and 17 tags.
- Only bone lengths differ slightly (`Bip01 Pelvis` 7.48 vs 5.34, thighs 5.85/6.59 vs 6.23). MDS
  keeps its own `parentDist`, so retargeted poses keep BJ's proportions.
- Both formats use 80-byte bone-info records and the same compressed frame layout
  (`short angles[4]`, `short ofsAngles[2]` per bone, plus a frame header with bounds, local origin,
  radius and parent offset).

### Animation source (decision D10)
ET's animations are the source: they exist and share the skeleton. CoD4/WaW animations are a fallback
only if the ET retarget fails. They are compiled `xanim` files on a different skeleton (`j_*` bones),
so they'd need a decompiler plus a real bone-mapping retarget. Report to the user before going there.

### Plan
0. **Reading aid:** ET: Legacy's renderer (`src/renderer/tr_animation_mdm.c` for MDM/MDX skinning, `tr_model.c` for loading, plus
   `src/game/g_mdx.c`, its server-side MDX skeleton code for hitboxes) is clean, commented
   reference code for the MDX format. Use it with ioRTCW's `tr_animation.c` (MDS) when writing the tool.
1. **Spike first (½ day):** write `tools/mdx2mds.py` (Python 3 stdlib only, run with `python3 -I`):
   - Read ET `body.mdx` and RTCW `body.mds`.
   - For each requested ET frame range, build MDS frames by copying the compressed bone records by
     bone name.
   - For the 17 `tag_*` bones, take each tag bone's pose relative to its parent from a reference BJ
     crouch frame and re-apply it to the new parent pose. This is the only real math. Check whether
     MDS angles are parent-relative or absolute while writing the spike (`tr_animation.c`
     `R_CalcBone`).
   - Append the frames, then rewrite `numFrames` and every offset after the frame block
     (`ofsBones`, `ofsSurfaces`, `ofsTags`, `ofsEnd`).
   - Output `models/players/bj2/body.mds` into a build folder.

   Convert only `prone_crawl` and check it with `cg_thirdPerson 1`. Stop and report if it looks broken.
2. **Animation config:** append entries for the new frames to a copy of
   `models/players/bj2/wolfanim.cfg`: `prone_idle`, `prone_crawl`, `prone_crawl_bk`, `prone_down`,
   `prone_up`, and rifle/pistol variants if wanted.
3. **Code:**
   - Add `ANIM_MT_PRONE`, `ANIM_MT_PRONEBK`, `ANIM_MT_IDLEPRONE` to the move-type enum (`bg_public.h:1511`,
     before `NUM_ANIM_MOVETYPES`, which stays < 32 for the bitflags) and to `animMoveTypesStr`
     (`bg_animation.c:78`).
   - In `PM_Footsteps`, pick them when `COD_SF_PRONE` is set.
   - Optionally add `ANIM_ET_PRONE_TO_CROUCH`-style events. RTCW already has the enum entry.
   - `animModelInfo_t` grows. Both modules must be rebuilt together, which they always are.
4. **Script:** add `idleprone` / `prone` / `pronebk` blocks to a copy of `bj2/wolfanim.script`,
   modelled on ET's `human_base.script` (135 prone references) and RTCW's existing crouch blocks.
5. **Packaging:** `scripts/build-et-anims.sh` extracts from the user's ET install and writes
   `run/codmod/zz_codmod_etanims.pk3` (git-ignored, **never committed or shared**: ET assets
   aren't redistributable). The mod must work without this pk3. Then the body falls back to crouch anims.
6. **Polish:** third-person torso pitch and leg swing look odd lying down. Limit torso pitch while
   prone in `CG_PlayerAngles` (ET does similar).

### Acceptance (tier B)
- [ ] With `cg_thirdPerson 1`: the prone idle, crawl and transitions look right with the main
      weapons (no exploding limbs, weapon in hand, head attached).
- [ ] Without the pk3 the game still runs with crouch anims.
- [ ] Report, then **stop**.
