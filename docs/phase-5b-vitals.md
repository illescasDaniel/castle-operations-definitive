# Phase 5b — Health, stamina & vital HUD

**Prerequisite:** Phase 5.5 quickknife confirmed.
**Read first:** [architecture.md](architecture.md), [reference-values.md](reference-values.md).
Comes **before** [phase-6-slide.md](phase-6-slide.md).

## Goal

CoD-like survivability and exertion read:

1. **Health auto-regenerates** after a short delay without taking damage (CoD4-style).
2. **Stamina** drains/recharges like CoD4 (RTCW already close after Phase 2 — finish the remaining feel gaps).
3. **HUD:** health as a **bar** (not only a number), matching the stamina bar style; **both bars horizontal**.

Player only. AI / monsters keep vanilla health and never use this HUD.

## Behaviour

### 5b.1 Health regeneration

Vanilla SP only heals via pickups / `PW_REGEN`. Add player-only CoD regen in `ClientThink_real` / `ClientTimerActions` (or a small `g_cod.c` tick):

| Cvar | Default | Role |
|---|---|---|
| `cod_vitalsEnable` | 1 | Master for regen + stamina feel + vital HUD overrides |
| `cod_healthRegenEnable` | 1 | Auto regen on/off |
| `cod_healthRegenDelay` | 5000 | ms after last damage before regen starts (CoD4 `scr_player_healthregentime` ≈ 5) |
| `cod_healthRegenRate` | 20 | HP per second once regen is active (tunable; CoD4 MP uses chunked ticks — linear rate is fine for SP feel) |
| `cod_healthRegenPauseHurt` | 1 | Any damage resets the delay timer |

**Hooks:**

- On player damage in `G_Damage` (when `targ` is the human client and health drops): stamp `client->codLastDamageTime = level.time`.
- Each frame / residual tick: if `level.time - codLastDamageTime >= delay` and `health < max`, add `rate * dt`, clamp to `STAT_MAX_HEALTH`.
- Do **not** regen while dead, in intermission, or when `cod_enable` / `cod_vitalsEnable` / `cod_healthRegenEnable` is off.
- Keep overheal countdown and `PW_REGEN` behaviour; auto-regen only fills up to max (not overheal).
- Health kits / food still work as vanilla.

Optional later (not required for gate): low-health screen pulse already exists in `cg_newdraw.c` — leave unless it fights the new bar.

### 5b.2 Stamina (CoD-like finish)

Phase 2 already made drain/recharge **time-based** (`cod_sprintTime` 4s, `cod_sprintRechargeTime` 5s, min start, forward-only). Remaining vanilla leftovers that still feel “not quite CoD”:

| Quirk (current player path in `PM_Sprint`) | CoD4-like target |
|---|---|
| Extra ×2 recharge while bar > 25% (`sprintTime > 5000`) | Single linear recharge rate |
| Extra recharge while standing still | No bonus — same rate standing or walking |
| Recharge starts the instant sprint ends | Optional short delay (`cod_sprintRechargeDelay`, default ~500–800 ms) before recharge |

Keep: 0..20000 range, `PW_NOFATIGUE`, jump cost (`cod_sprintJumpCost`), drain only while moving (>128), `COD_SF_SPRINTING` gate.

| Cvar | Default | Role |
|---|---|---|
| `cod_sprintLinear` | 1 | When on: single-rate recharge (no 25% / idle bonuses) |
| `cod_sprintRechargeDelay` | 600 | ms after sprint ends before recharge starts (0 = immediate) |

Expose under `/cod_menu` **SPRINT** / new **VITALS** section.

### 5b.3 Horizontal health + stamina bars

Vanilla `ui/hud.menu` (in `sp_pak1.pk3`):

- Stamina: vertical strip `rect 10 400 10 70`, ownerdraw `CG_STAMINA` (no `align` → `CG_DrawFatigue` uses `BAR_VERT`).
- Health: number via `CG_PLAYER_HEALTH` in the Status block.

**Changes:**

1. **Cgame:** draw health as a filled bar (same family as `CG_DrawFatigue` / `CG_FilledBar`), frac = `STAT_HEALTH / STAT_MAX_HEALTH` (clamp). Prefer a dedicated ownerdraw (e.g. `CG_PLAYER_HEALTH_BAR`) **or** bar mode when the menu item has bar-sized rect + align — pick the smaller hook; keep numeric draw available behind a cvar if useful (`cod_healthBarNumber 0`).
2. **Menu override:** ship `ui/hud.menu` (and `ui/menudef.h` include if needed) from `mod/codmod/` via a small pk3 (`zz_codmod_hud.pk3`) so `fs_game codmod` wins over `sp_pak1`. Layout sketch (virtual 640×480):

| Element | Approx rect | Align |
|---|---|---|
| Health bar | bottom-left, wide short (e.g. ~120×10) | `HUD_HORIZONTAL` |
| Stamina bar | directly above or below health, same width | `HUD_HORIZONTAL` |

Stack them as a pair (CoD-ish bottom-left vitals). Drop or hide the big health **number** by default; optional small number overlay is fine if it stays readable.

3. `CG_DrawFatigue` already supports horizontal when `align == HUD_HORIZONTAL` — menu change may be enough for stamina; verify color ranges still read well on a short bar.

`cod_vitalsEnable 0` → restore vanilla HUD (no mod pk3 ownerdraw path / skip bar replace) and vanilla stamina quirks + no auto regen.

## Files

| Area | Touch |
|---|---|
| Tuning | `bg_cod.h` / `bg_cod.c`, `/cod_menu` **VITALS** |
| Regen | `g_combat.c` (last-damage stamp), `g_active.c` or `g_cod.c` (tick), `g_local.h` (`codLastDamageTime`) |
| Stamina | `bg_pmove.c` `PM_Sprint` player branch |
| Health bar | `cg_newdraw.c` (+ ownerdraw id in shared menudef if new) |
| HUD layout | `mod/codmod/ui/hud.menu` → packed `codmod_hud.pk3` (copy into `run/codmod/`). **Do not** name it `zz_*` — ioRTCW rewrites `zz_`→`sp_` when opening pak paths |
| Defaults | `mod/codmod/codmod.cfg`, [reference-values.md](reference-values.md) |

## Acceptance

- [ ] Take damage, wait ~5s without hits: health returns to full; another hit mid-regen restarts the delay
- [ ] `cod_healthRegenEnable 0` / `cod_vitalsEnable 0`: no auto regen (pickups still work)
- [ ] Sprint empties in ~`cod_sprintTime` s; recharges linearly in ~`cod_sprintRechargeTime` after delay (no sudden “fast top 75%” feel)
- [ ] Health and stamina show as **horizontal** bars; no vertical stamina strip; health not number-only
- [ ] AI health / behaviour unchanged; `cg_showmiss 1` clean while sprinting and regenerating

**Built 2026-10-08** (vitals confirmed; ammo scale + interact hint follow-up shipped). HUD: `mod/codmod/codmod_hud.pk3`.

### Follow-ups (same phase)

| Feature | Cvar / detail |
|---|---|
| Double ammo | `cod_ammoScale` 2 — player `Add_Ammo` grants + max carry; AI unchanged |
| Interact hint | `cod_interactHint` 1 — “Press \<key\> to interact” beside door/activate cursor hints; key from `+activate` bind |

## Gate

Vitals confirmed. Ammo + interact hint confirmed. Next: [phase-5c-hud.md](phase-5c-hud.md), then Phase 6 (slide).
