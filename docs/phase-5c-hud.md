# Phase 5c — CoD-style on-screen HUD

**Prerequisite:** Phase 5b (vitals + ammo scale + interact hints) confirmed.
**Read first:** [architecture.md](architecture.md), current `mod/codmod/ui/hud.menu`.
Comes **before** [phase-6-slide.md](phase-6-slide.md).

## Goal

Make the in-game HUD read like a modern FPS (zombies-mode ammo cue, CoD4-style
vitals feedback) instead of RTCW’s bar/number strip:

1. **Ammo:** single bottom-right readout `clip/reserve` (e.g. `20/30`) — BO Zombies style.
2. **No stamina bar** — stamina **gameplay is unchanged** (Phase 5b drain/recharge/delay still
   work); only the on-screen bar is removed. No other stamina indicator is required.
3. **No health bar** — low health via **bloody / vignette screen** plus a **crosshair colour
   ramp** (white → yellow → orange → red), not a meter.
4. **Overheat** (MG / Sten / etc.): no heat bar — ammo text uses the same colour ramp as heat
   builds (white → yellow → orange → red).
5. Light polish so the remaining chrome matches that look (see §5c.5).

Player only. AI / monsters unchanged. Debug HUD (`cod_debugHud`) and `/cod_menu` stay.

## Behaviour

### 5c.1 Combined ammo (`clip/reserve`)

Vanilla / Phase 5b HUD draws two ownerdraws:

| Ownerdraw | Value |
|---|---|
| `CG_PLAYER_AMMOCLIP_VALUE` | rounds in magazine (`ps->ammoclip[...]`) |
| `CG_PLAYER_AMMO_VALUE` | reserve pool (`ps->ammo[...]`) |

**Target (BO Zombies):** one string, bottom-right: **`%i/%i`** = clip / reserve.
Example: magazine 20, reserve 30 → `20/30`.

**Cgame:** extend `CG_DrawPlayerAmmoValue` (or a small `CG_CodDrawAmmo`) so when
`cod_hudEnable` is on it paints the combined string in one rect. Prefer clip digits larger
(or same scale with clear separation); reserve after the slash can be slightly smaller if
cheap.

**Ammo colour** (see §5c.3 for the shared ramp helper):

1. If the current weapon can overheat (`ammoTable[weap].maxHeat > 0`) and
   `ps->curWeapHeat > 0`: colour by **heat fraction** `curWeapHeat / 255`
   (white → yellow → orange → red as it overheats). Full red at / near overheat lockout.
2. Else: low-ammo colour by **clip fraction** (same ramp, or keep today’s red/yellow bands
   when nearly empty). Cool + full mag → white / default.

**Special weapons** (same early-outs as today):

- Knife / class special: no ammo text.
- Grenades / dynamite / flamer / tesla: show clip only (or `N` without `/reserve`) — they
  already skip reserve in type-0 path. Heat colour only if that weapon actually uses heat.
- Akimbo: keep a readable dual-clip presentation (e.g. `L/R` or `a+b/reserve`); do not
  regress the special-case path.

**Menu:** collapse the two ammo text items into one `itemDef` (wider bottom-right rect,
larger `textscale`). Remove the `CG_PLAYER_WEAPON_HEAT` bar item — heat is colour only.
Weapon icon optional (see §5c.5).

| Cvar | Default | Role |
|---|---|---|
| `cod_hudEnable` | 1 | Master for CoD HUD presentation (ammo style, hide bars, low-HP blood/crosshair) |
| `cod_hudAmmoStyle` | 1 | `1` = `clip/reserve`; `0` = vanilla split clip + reserve |
| `cod_hudHeatColor` | 1 | Ammo text white→red by `curWeapHeat` on heatable weapons |

### 5c.2 Hide stamina + health bars (gameplay unchanged)

Phase 5b shipped horizontal bars in `mod/codmod/ui/hud.menu` (`Health`, `Stamina` menus).

**Changes:**

1. Remove (or `visible MENU_FALSE`) those menuDefs from the mod `hud.menu`.
2. **Stamina still works exactly as Phase 5b left it** — time-based drain, linear recharge,
   recharge delay, jump cost, `cod_sprintTime` / `cod_sprintRechargeTime`, etc. Only the
   visual bar is gone; the player feels empty stamina by stopping sprint, not by reading a meter.
3. Health **regen** stays under `cod_vitalsEnable` — only the on-screen health bar goes away.
4. `cod_hudEnable 0` → simplest: delete bar menus permanently; bars were an interim 5b read.
   Off only reverts ammo style + blood/crosshair HUD extras.

### 5c.3 Shared colour ramp + health crosshair

One small helper (e.g. `CG_CodThreatColor( float t, vec4_t out )`) maps `t` in `[0,1]` through:

| `t` | Colour |
|---|---|
| 0.0 | white |
| ~0.33 | yellow |
| ~0.66 | orange |
| 1.0 | red |

Use for:

| Signal | Input `t` | Where |
|---|---|---|
| Weapon heat | `curWeapHeat / 255` | Ammo text (§5c.1) |
| Low health | `1 - health/maxHealth` | Crosshair (and ADS center-dot) |

**Crosshair:** vanilla already has `cg_crosshairHealth` + `CG_ColorForHealth`, but that ramp
assumes ~100 HP (+ armor) and goes greenish/cyan — wrong for `cod_maxHealth 50` and not the
requested white→red path. When `cod_hudEnable` is on, replace that path with the shared ramp
from health fraction (ignore armor for the tint). Respect `cg_crosshairHealth 0` = leave
crosshair untinted. Apply to both the hip crosshair and the Phase 3 ADS center-dot.

| Cvar | Default | Role |
|---|---|---|
| `cod_hudHealthCrosshair` | 1 | Crosshair/dot white→red by missing health (needs `cg_crosshairHealth 1`) |

### 5c.3b CoD 4-post dynamic crosshair (follow-up)

Replace the vanilla scaled shader with a procedural **4-post** reticle (`CG_CodDrawCrosshair`):

| Behaviour | Detail |
|---|---|
| Idle / crouch | Tight center gap (`cod_crosshairGap`; crouch × `cod_crosshairCrouchScale`) |
| Walk / run / sprint | Gap blooms with XY speed (`cod_crosshairMoveBloom`) + fire `aimSpreadScale` (`cod_crosshairBloom`); sprint also fades posts (`cod_crosshairSprintAlpha`) |
| ADS | Posts fade out with ADS frac; **center dot stays** while `cod_adsCrosshair 1` (interim until per-weapon iron-sight tune → then `2` hides the dot) |
| Contrast | Optional 1px black outline (`cod_crosshairOutline`) |
| Health tint | Same §5c.3 ramp when `cod_hudHealthCrosshair` is on |

| Cvar | Default | Role |
|---|---|---|
| `cod_crosshairStyle` | 1 | `1` = CoD posts; `0` = vanilla shader |
| `cod_crosshairGap` | 4 | Base half-gap (640 coords) |
| `cod_crosshairLength` | 8 | Post length |
| `cod_crosshairWidth` | 2 | Post thickness |
| `cod_crosshairDot` | 1 | Hip-fire center dot |
| `cod_crosshairBloom` | 16 | Extra gap from `aimSpreadScale` |
| `cod_crosshairMoveBloom` | 14 | Extra gap at full sprint speed |
| `cod_crosshairCrouchScale` | 0.55 | Gap multiplier while crouching |
| `cod_crosshairSprintAlpha` | 0.35 | Post alpha at full sprint |
| `cod_crosshairOutline` | 1 | Black outline for contrast |

Hit markers are E9 (`cod_hitMarker*`; `/cod_menu` → **HIT MARKER**). Tune crosshair live: `/cod_menu` → **CROSSHAIR**.

### 5c.4 Low-health “bloody” screen

RTCW already has hit feedback:

- `CG_DamageBlendBlob` — directional blood sprites (`viewBloodBlend*`)
- `CG_DrawFlashDamage` — short full-screen red flash on damage
- Menu flag `CG_SHOW_HEALTHCRITICAL` when `STAT_HEALTH < 25`

**Missing for CoD feel:** a **persistent** blood/vignette while health is low that eases off
as regen fills you up (not only a hit flash).

**Approach (cgame-only):**

1. In `CG_Draw2D` (near `CG_DrawFlashDamage`), call `CG_CodDrawLowHealthBlood()`.
2. While alive and `cod_hudEnable && cod_hudLowHealthBlood`:
   - `frac = 1 - health/maxHealth` (clamp).
   - Below `cod_hudLowHealthStart` (fraction of max, default ~0.4 → with `cod_maxHealth 50`
     that is 20 HP), ramp alpha of a full-screen dark-red / blood overlay.
   - Prefer existing media (`viewFlashBlood`, `viewBloodBlend*`) or a soft `CG_FillRect`
     vignette if shaders look too “hit spat”. Pulse gently when critically low
     (`health/max < ~0.2`) so regen feels visible.
3. Respect `cg_blood 0` (player turned blood off).
4. Do not draw when dead, in intermission, or `cg.cameraMode`.

| Cvar | Default | Role |
|---|---|---|
| `cod_hudLowHealthBlood` | 1 | Persistent low-HP blood/vignette |
| `cod_hudLowHealthStart` | 0.4 | Start overlay when health/max ≤ this |
| `cod_hudLowHealthMaxAlpha` | 0.55 | Cap overlay opacity at near-death |

Hit flashes and directional blood stay; they layer on top. Crosshair colour (§5c.3) is a
second health read that still works if blood is disabled.

### 5c.5 Other CoD-ish polish (in scope for this phase)

Do these with the same `hud.menu` / ammo pass — small, high leverage:

| Item | Default | Notes |
|---|---|---|
| No weapon **heat** bar | on | Drop `CG_PLAYER_WEAPON_HEAT`; heat = ammo text colour (§5c.1) |
| Weapon icon | keep, smaller / above ammo | Optional; if noisy, hide behind `cod_hudWeaponIcon 0` |
| Ammo placement | bottom-right, larger | Classic CoD corner; virtual 640×480 rect ~`480 430 150 40` (tune in playtest) |
| Interact hints | keep Phase 5b | “Press F…” / “Breakable” unchanged |
| Holdable icon | keep | Compact; no new art |

**Out of scope here** (stay in Phase 7 unless you ask mid-phase): hit markers (E9), menu
options packing (E10), FOV/sensitivity UI (E14–E16).

## Files

| Area | Touch |
|---|---|
| Ammo + heat colour | `cgame/cg_newdraw.c` (`CG_DrawPlayerAmmoValue` / new helper) |
| Threat colour helper | `cgame/cg_cod.c` (or `cg_drawtools.c`) — shared white→red ramp |
| Crosshair health tint | `cgame/cg_draw.c` (hip + ADS dot; replace `CG_ColorForHealth` when hud on) |
| CoD 4-post crosshair | `cgame/cg_cod.c` `CG_CodDrawCrosshair`, hooked from `CG_DrawCrosshair` |
| Low-HP blood | `cgame/cg_draw.c` (+ helper in `cg_cod.c` if cleaner) |
| Cvars | `bg_cod.h` / `bg_cod.c`, `/cod_menu` **HUD** / **CROSSHAIR** |
| Layout | `mod/codmod/ui/hud.menu` → rebuild `codmod_hud.pk3` (still **not** `zz_*`) |
| Defaults | `mod/codmod/codmod.cfg`, [reference-values.md](reference-values.md) |

## Acceptance

- [x] Ammo shows as `clip/reserve` (e.g. `20/30`); firing decreases left number; reload moves from right to left
- [x] No health bar and no stamina bar on screen
- [x] Sprint still drains/recharges as in Phase 5b; empty stamina still stops sprint (feel only, no bar)
- [x] Heatable weapons: holding fire warms ammo text white → yellow → orange → red; no heat bar
- [x] Crosshair (and ADS dot) shifts white → yellow → orange → red as health drops; recovers with regen
- [x] At low health the screen looks bloody / vignetted; effect fades as health regens
- [x] `cg_blood 0` disables the blood overlay (crosshair tint still ok); `cg_crosshairHealth 0` disables tint
- [x] `cod_hudEnable 0` restores split ammo (and disables low-HP overlay / CoD crosshair ramp); vitals gameplay still follows `cod_vitalsEnable`
- [x] Knife / grenades / specials still look sane; AI / prediction unaffected
- [x] 4-post crosshair blooms with move/fire; ADS fades posts but keeps center dot (`cod_adsCrosshair 1`)

**HUD confirmed 2026-10-09.** Crosshair bloom committed 2026-10-09.

## Gate

Phase 5d (binds / toggle crouch / flashlight / reload anim), then Phase 6 (slide).
Hit markers are E9 (done).
