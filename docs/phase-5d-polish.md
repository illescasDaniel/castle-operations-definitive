# Phase 5d — Binds, toggle crouch, health clamp, flashlight, reload anim

**Prerequisite:** Phase 5c (CoD HUD) confirmed.
**Read first:** [architecture.md](architecture.md).
Comes **before** [phase-6-slide.md](phase-6-slide.md).

## Goal

Polish before slide:

1. **Full keybind reset** to codmod defaults (including new binds), via `--reset-binds`, first launch, menu Defaults, and `/cod_resetbinds`.
2. **Toggle crouch** on `C` (not hold).
3. **Health packs** never raise player HP above `cod_maxHealth` (50).
4. **Flashlight** toggle on `L` (RTCW SP has none).
5. **Reload animation** always plays for auto and manual reload.

Player only where relevant. AI unchanged.

## Behaviour

### 5d.1 Full bind reset

[`mod/codmod/codmod_binds.cfg`](../mod/codmod/codmod_binds.cfg) is a complete reset:

1. `unbindall`
2. `exec default.cfg` (vanilla from `pak0.pk3`)
3. Codmod deltas: ADS, unbind CTRL, quickknife, F activate, toggle crouch, flashlight

Applied on: first launch (no `wolfconfig.cfg`), `scripts/run.sh --reset-binds`, menu Defaults when `fs_game` is `codmod`, and console `/cod_resetbinds` / `/exec codmod_binds.cfg`.

Every-launch [`codmod.cfg`](../mod/codmod/codmod.cfg) still `unbind CTRL` as a safety net.

### 5d.2 Toggle crouch (`C`)

Cgame `togglecrouch`: sticky `+movedown` / `-movedown` (same pattern as `toggleads`).
Auto-stand when jump is pressed (jump and crouch share `upmove`). Hold crouch still available via `bind c +movedown`.

### 5d.3 Health pack clamp

In `Pickup_Health`, when cod vitals are on and the picker is the human player, always clamp to `STAT_MAX_HEALTH` (no 2× overheal for small/mega). Per-frame clamp in `ClientThink_real` remains.

### 5d.4 Flashlight (`L`)

Client-local: `toggleflashlight` + per-frame `CG_Spotlight` cone/core/impact (with `SL_NOMODEL`) plus forced dlights along the view ray.
Cvars: `cod_flashlightEnable`, `cod_flashlightIntensity`, RGB. No FP lamp model.

### 5d.5 Reload animation

`PM_BeginWeaponReload` always starts `WEAP_RELOAD1` (clear `weapAnimTimer`; use `PM_StartWeaponAnim`).
Cgame clears weap lerp on reload so hands do not skip after fire. Covers empty-clip auto-reload and manual `R`.

## Files

| Area | Touch |
|---|---|
| Binds | `mod/codmod/codmod_binds.cfg`, `codmod.cfg`, `scripts/run.sh` (docs only if needed) |
| Menu Defaults | `ui/ui_main.c` `resetDefaults` |
| Toggle crouch / flashlight / resetbinds | `cgame/cg_cod.c`, `cg_consolecmds.c`, `cg_local.h` |
| Flashlight draw | `cg_cod.c` (or view draw hook) |
| Cvars | `bg_cod.h` / `bg_cod.c`, `codmod.cfg` |
| Health clamp | `game/g_items.c` `Pickup_Health` |
| Reload anim | `game/bg_pmove.c`, `cgame/cg_weapons.c` |

## Acceptance

- [ ] `--reset-binds` / first launch / menu Defaults / `/cod_resetbinds`: ADS, V quickknife, C toggle crouch, L flashlight, CTRL unbound
- [ ] Tap C: stay crouched; tap again: stand; jump while crouched: stand and jump
- [ ] Health packs never leave HP above 50
- [ ] L toggles a visible view light in dark areas
- [ ] Empty clip with reserve: reload anim plays; manual R with partial clip: same
- [ ] Sprint / ADS / quickknife still work

## Gate

Phase 6 (slide) after in-game confirm.
