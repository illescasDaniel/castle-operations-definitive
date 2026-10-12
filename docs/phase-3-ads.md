# Phase 3 — Aim Down Sights (ADS)

**Prerequisite:** Phase 2 confirmed. The tuning framework, debug HUD, and `STAT_COD_*` exist.
**Read first:** [architecture.md](architecture.md).

## Design summary

| Layer | What | Where |
|---|---|---|
| Input | Hold `MOUSE2` → `+ads` alias → `+wbutton6` → `WBUTTON_EXTRA6` | `mod/codmod/codmod.cfg` (aliases) + `codmod_binds.cfg` (binds), no engine change |
| State (shared, predicted) | ADS fraction 0..1000 in `stats[STAT_COD_ADS]`, advanced by time in pmove | `bg_pmove.c` + `bg_cod.c` |
| Gameplay | Move speed × lerp(1, adsMoveScale), no sprint while ADS, tighter spread | `bg_pmove.c`, `g_weapon.c` |
| Visual | Viewmodel lerps to a per-weapon "sight" offset, less bob/sway, FOV zoom, sensitivity scale, crosshair fade | `cg_weapons.c`, `cg_view.c`, `cg_draw.c`, `cg_cod.c` |
| Scoped rifles | Hold right-click = real RTCW scope (automatic `weapalt` in, out on release), section 3.8 | `cg_cod.c`, `cg_weapons.c`, `bg_pmove.c` (switch time) |

"Secondary fire / right click" in the brief: RTCW's `+attack2` (`WBUTTON_ATTACK2`) is
barely used and right-click is bound to jump by default. We **don't** reuse
`WBUTTON_ATTACK2`, because it is referenced by firing and intermission code
(`bg_pmove.c` ~L3076, `g_active.c` ~L450, ~L556). We use the free `WBUTTON_EXTRA6` and rebind `MOUSE2`.

---

## 3.1 Input

`bg_public.h`: `#define WBUTTON_COD_ADS WBUTTON_EXTRA6  // codmod: bound via +wbutton6 / +ads`
(verify with grep that `WBUTTON_EXTRA6` has no other users).

`mod/codmod/codmod.cfg` additions (aliases, every launch):
```
alias +ads "+wbutton6"
alias -ads "-wbutton6"
// toggle variant (see below)
set ads_tog "vstr ads_on"
set ads_on  "+wbutton6; set ads_tog vstr ads_off"
set ads_off "-wbutton6; set ads_tog vstr ads_on"
alias toggleads "vstr ads_tog"
```
`mod/codmod/codmod_binds.cfg` additions (first launch only, see phase 1.7):
```
bind MOUSE2 "+ads"        // was +moveup (jump). SPACE is already +moveup in vanilla
```
**Toggle ADS needs no engine change:** a `+button` command run without a key number (from `vstr`)
stays down until the matching `-button` (`IN_KeyDown`/`IN_KeyUp`, `client/cl_input.c:73-122`).
So `bind MOUSE2 toggleads` gives toggle ADS. Document both in the phase report. Hold is the
default (decision D3). Known toggle caveat: the button stays logically down through death,
reload and weapon switch. That is fine, because the ADS rules (3.3) already ease out and then resume.

## 3.2 Per-weapon gameplay table (shared) — `bg_cod.c`

```c
typedef struct {
	qboolean canADS;
	float moveScale;     // 0 => use cod_adsMoveScale
	float fovScale;      // 0 => use cod_adsFovScale
	int   timeIn, timeOut; // ms; 0 => cvar default
	float spreadScale;   // 0 => use cod_adsSpreadScale
} codWeaponTuning_t;
extern const codWeaponTuning_t bg_codWeapons[WP_NUM_WEAPONS];
qboolean BG_CodCanADS( const playerState_t *ps );
```

Initial eligibility:

| ADS | Weapons |
|---|---|
| **Yes** | `WP_LUGER`, `WP_SILENCER`, `WP_COLT`, `WP_MP40`, `WP_THOMPSON`, `WP_STEN`, `WP_MAUSER` (iron sights), `WP_GARAND` (iron sights), `WP_FG42` (unscoped) |
| Scope instead of ADS (3.8) | `WP_MAUSER` when the player owns `WP_SNIPERRIFLE`, `WP_GARAND` when they own `WP_SNOOPERSCOPE`, `WP_FG42` (always has `WP_FG42SCOPE`), and the scoped variants themselves (decision D4) |
| No (not aimable / CoD4 parity) | `WP_KNIFE`, `WP_GRENADE_LAUNCHER`, `WP_GRENADE_PINEAPPLE`, `WP_DYNAMITE`, `WP_AKIMBO`, `WP_FLAMETHROWER`, `WP_TESLA`, `WP_VENOM`, `WP_PANZERFAUST` (panzer can be revisited later), monster/MP-only weapons |

Suggested per-class starting values: pistols `timeIn 150`, `fovScale 0.85`, `moveScale 0.7`.
SMGs `200 / 0.82 / 0.6`. Rifles (Mauser, Garand, FG42) `260 / 0.75 / 0.5`.

`BG_CodCanADS(ps)` = `!aiChar && enabled && bg_codWeapons[weapon].canADS && weaponstate not in
{RAISING*, DROPPING*, RELOADING} && !(eFlags & (EF_ZOOMING|EF_MG42_ACTIVE|EF_MELEE_ACTIVE))
&& waterlevel < 3 && !ladder` (phase 5 adds the slide rule, phase 5b the prone rules).

## 3.3 Pmove state

`static void PM_CodUpdateADS( void )` in `bg_pmove.c`, called in `PmoveSingle` before
`PM_CodUpdateSprint` (ADS has priority over sprint):
```c
want = ( pm->cmd.wbuttons & WBUTTON_COD_ADS ) && BG_CodCanADS( pm->ps );
frac = pm->ps->stats[STAT_COD_ADS];                  // 0..1000
frac += ( want ? +1 : -1 ) * 1000 * pml.msec / ( want ? timeIn : timeOut );
clamp 0..1000; store.
```
- Changing weapon or starting a reload forces `want = qfalse`, so it slides out naturally.
- `PM_CodUpdateSprint`: add `&& !( cmd.wbuttons & WBUTTON_COD_ADS )` to `wantSprint`.
  Holding ADS blocks or cancels sprint, as in CoD4.
- `PM_CmdScale` (player path): `scale *= 1 + ( moveScale - 1 ) * frac/1000`.
- AI: `PM_CodUpdateADS` returns immediately and keeps `stats[STAT_COD_ADS] = 0` when `ps->aiChar`.

## 3.4 Spread (gunplay)

`game/g_weapon.c` ~L1660-1725 (`aimSpreadScale` from `client->currentAimSpreadScale`): for
non-AI clients, multiply by `1 + ( spreadScale - 1 ) * frac/1000` before it's used. Also look
at the other spread paths (~L1635 `spreadfrac`, `weapon_venom_fire`) for the same treatment.
`PM_AdjustAimSpreadScale` (`bg_pmove.c:2550`) stays vanilla. ADS simply multiplies its result.

## 3.5 Viewmodel centering — `cgame`

Cgame-only per-weapon sight offsets (`cg_cod.c`):
```c
typedef struct { float fwd, right, up, pitch, yaw, roll; } codAdsView_t;
extern codAdsView_t cg_codAdsView[WP_NUM_WEAPONS];   // not const: live-tuning writes here
```
1. `CG_AddViewWeapon` (`cg_weapons.c` ~L3024): after the `gunoff`/`fovOffset` `VectorMA`s,
   add `ads.{fwd,right,up} * e` along `cg.refdef.viewaxis[0..2]`, with
   `e = smoothstep( stats[STAT_COD_ADS] / 1000 )` read from `cg.predictedPlayerState`.
   Add `ads.{pitch,yaw,roll} * e` to `angles` before `AnglesToAxis`.
2. `CG_CalculateWeaponPosition` (`cg_weapons.c:1712`): scale the bob angles, land-dip, and
   idle drift by `1 - e * cod_adsBobScale` (default 0.85). Keep lean handling.
3. **Expect imperfect sights.** RTCW viewmodels were never authored for ADS. Some will align
   with real iron sights and others will only look "raised & centered". That's acceptable,
   and the goal is the CoD *feel*. The muzzle flash and brass come from model tags, so they follow
   automatically.
4. FOV zoom also magnifies the viewmodel, because id Tech 3 draws it in the main scene with
   `RF_DEPTHHACK`. Offsets are tuned **with** zoom applied. If the gun looks too big, add
   `cod_adsGunFovComp` to push the model forward in proportion to the zoom.
5. If the gun clips at the near plane when moved close (`r_znear` default 4, cheat-protected),
   push it forward rather than touching `r_znear`.

### Status (2026-10-09)

- **Core ADS accepted** for the Luger/pistol (in-game). Phase 4 (gait) may proceed.
- **Per-weapon iron-sight bake done** from `codmod_ads_tune.log` (all 9 weapons, final
  pass 2026-10-09). Globals default to 0; `cod_adsCrosshair 2`. Use
  `cod_adsCrosshairForce 1` (or `/cod_adsTuneStart`) to keep the reticle while ADS for
  re-tune. Tune tooling kept.

### Alignment tooling (required: this is how offsets get tuned)

**Per-weapon bake session** (closes the deferred Phase 3 item):

1. Launch with cheats (`devmap escape1` via `scripts/run.sh`).
2. `/cod_adsTuneStart` — sets `cod_adsLock 1` + `cod_adsTune 1`, loads the current weapon,
   prints the 9-weapon checklist. Then `/give all`.
3. For each iron-sight weapon: tweak via `/cod_menu` → **ADS TUNE** (Height/Barrel/Dist + fine
   bias) or `/set cod_adsTune*`, then `/cod_adsTuneSave`. Cycle with `/cod_adsTuneNext`.
4. Saves append to `run/home/codmod/codmod_ads_tune.log` (machine-parseable `ads_tune SAVE …`
   plus a pasteable C initializer). Latest SAVE per weapon wins.
5. Tell the agent you are done; it bakes the rows into `cg_codAdsView`, zeros the global
   iron-sight cvars, sets `cod_adsCrosshair 2`, rebuilds.

Weapons in scope: Luger, Silencer, Colt, MP40, Thompson, Sten, Mauser, Garand, FG42
(scopes stay on the real scope path — not this pass).

**Commands**

| Command | Role |
|---|---|
| `/cod_adsTuneStart` | Lock + tune mode, checklist, seed current weapon |
| `/cod_adsTuneNext` | Next of the 9 weapons + load |
| `/cod_adsTuneLoad` | Seed Tune* from current weapon (effective pose) |
| `/cod_adsTuneSave` | Append SAVE + C line to `codmod_ads_tune.log` |
| `/cod_adsTuneDump` | Append pasteable C line only (scratch) |

While `cod_adsTune 1`, the selected weapon's table row is an **absolute** pose (globals folded
in once). Tweaking one gun cannot shift another mid-session. After bake, globals default to 0
and the table holds the absolute values permanently.

**Also**

- **In-game console (`~`): prefix every command with `/`**, e.g. `/set cod_adsTuneHeight 3`.
  Without `/` the line may not run. (Plain `set` without `/` is fine inside `.cfg` files.)
- **Tune menu:** `/cod_menu` — ADS TUNE section has the new geometry knobs plus START / NEXT /
  LOAD / SAVE actions. General cvar dumps still go to `run/home/codmod/codmod_tune.log`.
- Global iron-sight knobs (`cod_adsSightHeight`, …) remain as a master offset on top of the
  table when not in adsTune mode. Luger defaults from `codmod_tune.log` (2026-10-08):
  Dist 20, Height 2.5, BarrelBack 13, Pitch -1, Yaw -3.5, Roll 6.5, Right 1.
- RTCW viewmodels were authored for hip-fire, not CoD iron sights — expect "raised & centered"
  more than pixel-perfect CoD alignment.

## 3.6 FOV & sensitivity — `cg_view.c` `CG_CalcFov` (L786)

- After the user FOV is resolved (`fov_x = cg_fov`) and **only when** no binocular or scope zoom is
  active (`!cg.zoomedBinoc && !cg.zoomval`): `fov_x *= 1 + ( fovScale - 1 ) * e`.
  Let the existing code derive `fov_y`.
- Sensitivity (~L918-935): in the non-zoom branch (`cg.zoomSensitivity = 1`), use
  `1 + ( fovScale * cod_adsSensScale - 1 ) * e` instead, so aim speed tracks the zoom.
  Don't change binocular or scope behaviour.

## 3.7 HUD

- `CG_DrawCrosshair` (`cg_draw.c`): while ADS (`e > 0.5`), `cod_adsCrosshair` controls the
  reticle — `1` (default) draws a center dot (interim until all weapons are tuned), `2` hides
  it completely, `0` keeps the hip crosshair.
- Debug HUD: show `ads` frac and current `fov`.
- Luger iron-sight defaults (from `codmod_tune.log`, 2026-10-08): Dist 20, Height 2.5,
  BarrelBack 13, Pitch -1, Yaw -3.5, Roll 6.5, Right 1.

## 3.8 Right-click on scoped rifles: hold to scope (decision D4)

Goal (user decision 2026-10-08): **every** firearm aims with right-click. Weapons without a scope
get iron-sight ADS (3.1-3.7). Rifles that have a scope in RTCW show their **real scope** while
right-click is held, and drop back to the unscoped rifle on release.

How vanilla scopes work: a scope is a separate weapon. `weapalt` (`CG_AltWeapon_f`,
`cg_weapons.c:3834`, `getAltWeapon` `:3622`) switches between pairs:
`WP_MAUSER ↔ WP_SNIPERRIFLE`, `WP_GARAND ↔ WP_SNOOPERSCOPE`, `WP_FG42 ↔ WP_FG42SCOPE`.
The scoped weapon is drawn as a full-screen scope with its own zoom and sensitivity. It's a normal
weapon change (`PM_BeginWeaponChange`, `bg_pmove.c` ~L2160-2215: drop + raise, "usually 1/4 sec"
each). Scoped weapons start at worst accuracy (`aimSpreadScale = 255`) and settle, which is RTCW's
sniper "steady your aim" mechanic. Keep it.

Implementation (cgame, because weapon selection is client-driven):
1. `cg_cod.c` `CG_CodUpdateScopeHold()`, called every frame from `CG_DrawActiveFrame` (before the
   usercmd weapon is read). Read the ADS button from the latest usercmd (`trap_GetCurrentCmdNumber` /
   `trap_GetUserCmd`, `wbuttons & WBUTTON_COD_ADS`).
2. **Press edge** on an unscoped rifle whose scoped alt is selectable (`CG_WeaponSelectable( getAltWeapon(w) )`):
   run the same path as `weapalt` (factor the body of `CG_AltWeapon_f` into
   `CG_CodAltWeapon( qboolean force )` that skips the `cg_weaponCycleDelay` check), and set
   `cg.codScopeByAds = qtrue`.
3. **Release edge** while `cg.codScopeByAds` and the current weapon is a scoped variant: switch back
   the same way and clear the flag. If the user scoped with the `weapalt` key (flag not set),
   right-click does nothing, so the vanilla workflow still works.
4. Queueing: if the release comes while the scope is still raising, remember it and switch back
   as soon as `weaponstate == WEAPON_READY` (the same for a press during a lowering).
   Never call the alt switch while `WEAPON_RELOADING` (vanilla rule).
5. Pmove side: `BG_CodCanADS` stays false for these rifles while the scope is owned, so iron-sight
   ADS never fights the scope. A Mauser **without** the scope uses iron-sight ADS.
6. **Scope speed** (`cod_scopeSwitchTime`, default 0 = vanilla): `PM_BeginWeaponChange` has an empty
   "different switch times for alt weapons" `switch ( newweapon )` (~L2212). For the player and the
   three rifle↔scope pairs, set `switchtime = cod_scopeSwitchTime` when it is > 0. Measure vanilla
   first (expect ~500 ms total). CoD4 sniper rifles scope in in roughly 300-400 ms. Tune with the user.
7. Empty-mag rule from vanilla stays: firing or reloading an empty scoped rifle switches to the
   unscoped rifle. `cg.codScopeByAds` must be cleared when that happens (weapon changed but not by us).
8. Movement while scoped: apply `cod_adsMoveScale` to the scoped variants too (pmove: treat the scoped
   weapons as "full ADS" for the move scale only). No viewmodel or FOV work: the vanilla scope does that.

## 3.9 Interactions checklist

| Situation | Expected |
|---|---|
| Hold ADS, press sprint | No sprint while ADS is held |
| Sprinting, press ADS | Sprint ends, ADS starts |
| ADS + crouch / lean | Allowed (CoD4) |
| ADS + prone (phase 5b) | Allowed while still. Eases out while crawling or during a stance transition |
| ADS + jump | Allowed. Spread uses vanilla airborne penalties |
| ADS + reload / weapon switch / `weapalt` | ADS eases out, and resumes after if still held |
| ADS + binoculars (`+zoom`) | Binoculars win and ADS eases out |
| Knife, grenades, other excluded weapons | ADS does nothing |
| Mauser (scope owned), Garand (Snooper owned), FG42 | Hold right-click: real scope. Release: back to the rifle. `weapalt` still toggles the scope the vanilla way |
| Scoped and the mag runs empty | Vanilla auto-switch to the rifle. Releasing right-click afterwards does nothing |
| Mounted MG42 | ADS does nothing |
| Death / cutscene / camera | ADS resets (frac decays, no FOV glitch on respawn or load) |

## Acceptance criteria (gate)

- [ ] Every "Yes" weapon: holding `MOUSE2` smoothly raises and centers the gun, zooms the FOV,
      hides the crosshair, and slows movement (check the HUD: jog 200 → ~100-140 depending on weapon).
- [ ] Release returns smoothly. Fast tapping never pops.
- [ ] Spread: 20 full-auto MP40 shots at a wall from ~10 m, hip vs ADS. The ADS group is visibly tighter.
- [ ] Excluded weapons: no change in behaviour.
- [ ] Scoped rifles: hold right-click → scope, release → rifle, at `com_maxfps 60` and `250`, with fast taps, during reloads and with an empty mag. `weapalt` still works.
- [ ] `cg_showmiss 1`: no prediction errors from ADS toggling.
- [ ] Enemies unaffected. Their accuracy and movement are the same as with `cod_adsEnable 0`.
- [ ] Alignment tooling works and is documented in the phase report, with a table of the shipped offsets.
- [ ] Report, then **stop**.
