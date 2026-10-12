# Reference Values: Vanilla RTCW vs CoD4 vs Mod Defaults

All speeds are in game units per second (u/s), horizontal.

## Scale sanity check

| | RTCW (verified in source) | CoD4 |
|---|---|---|
| Player box height | 72 (`playerMins z −24`, `playerMaxs z 48`) | ~70 |
| Stand eye height above feet | 64 (24 + `DEFAULT_VIEWHEIGHT 40`) | 60 |
| Crouch eye height above feet | 40 (24 + `CROUCH_VIEWHEIGHT 16`) | 40 |
| Prone eye height above feet | none in RTCW. ET: 16 (24 + `PRONE_VIEWHEIGHT −8`) | ~11 |
| Gravity | 800 (`g_gravity`) | 800 |
| Jump | `JUMP_VELOCITY 270` → ~45.6 u high | `jump_height 39` → ~250 u/s |

The world scales match within ~7%, so CoD4 absolute speeds can be used almost 1:1.

## Vanilla RTCW player (verified at ioRTCW `438e7d4`)

| Quantity | Source | Value |
|---|---|---|
| Base speed | `g_speed` | 320 |
| Jog | `runSpeedScale 0.8` | **256** |
| Sprint | `sprintSpeedScale 1.1` | **352** (1.375× jog) |
| Walk (`+speed` with `cl_run 1`) | input magnitude 64/127 | **~129** |
| Crouch | clamp `speed × crouchSpeedScale 0.25` | **80** |
| Back / strafe | none | same as forward |
| AI soldier (for comparison) | `ai_cast_characters.c` ~L56 table; overwritten every think from the anim `moveSpeed` (`ai_cast_think.c` ~L626-652) | run **~220**, walk ~90, crouch ~80. Measure in-game |
| Stamina | `sprintTime` 0..20000. Drain 50 **per pmove call**. Recharge 500/s (+500 if >5000, +500 if idle) | ~4.7 s at 85 fps, but frame-rate dependent |
| Accel / friction | `pm_accelerate 10`, `pm_friction 6`, `pm_stopspeed 100` | |
| Duck view lerp | `DUCK_TIME 100` ms, linear (cgame only. The bbox changes instantly) | |
| Lean | `LEAN_MAX 28` u offset, roll = `leanf/2` → **14°** max, in 280 ms, out 350 ms. Blocked while moving forward, crouch-jumping, or firing. Firing blocked while leaned | |
| FOV | `cg_fov 90` | |
| Spread | `aimSpreadScale` 0..255 (view-turn & movement based) | |

## CoD4 reference

Confidence: **H** = seen in CoD4 config files shipped in this machine's `iw_*.iwd`, or widely
documented. **M** = commonly cited, not verified here. **L** = estimate from memory or feel.

| Quantity | CoD4 | Conf. |
|---|---|---|
| `g_speed` (jog with a 1.0 weapon) | 190 | H |
| Sprint multiplier `player_sprintSpeedScale` | 1.5 | M |
| Sprint duration `player_sprintTime` | 4 s (MP default; `scr_player_sprinttime 4`) | H |
| Sprint min charge to restart `player_sprintMinTime` | 1.0 s | M |
| Crouch `player_duckedSpeedScale` | 0.65 | M |
| Prone `player_proneSpeedScale` | 0.15 (ET `pm_proneSpeedScale` 0.21) | M |
| Back `player_backSpeedScale` | 0.7 | M |
| Strafe `player_strafeSpeedScale` | 0.8 | M |
| Weapon `moveSpeedScale` | ~0.875 (LMG) … 1.0 (SMG/pistol) | L |
| ADS move speed | roughly 0.5–0.6 × jog | L |
| ADS FOV | weapon `adsZoomFov` ~50–55 vs `cg_fov 65`, so ×0.78–0.85 | L |
| ADS transition | weapon `adsTransInTime` ~200–300 ms in, ~150–250 ms out | L |
| View bob amplitudes | standing ".04 .017", ducked ".03 .02", sprinting ".043 .0215" | H (found in shipped cfgs) |

## Mod defaults (`cod_*` cvars) — the starting point for tuning

| Cvar | Default | Result | Rationale |
|---|---|---|---|
| `cod_runSpeed` | 200 | jog 200 | CoD4 190 × (64/60 eye-height ratio) ≈ 203 |
| `cod_sprintScale` | 1.5 | sprint 300 | CoD4 |
| `cod_walkScale` | 0.45 | walk 90 | "slower stealth walk" from the brief. CoD4 has no walk key |
| `cod_crouchScale` | 0.65 | crouch 130 | CoD4. Much faster than vanilla 80 |
| `cod_backScale` | 0.7 | back 140 | CoD4 |
| `cod_strafeScale` | 0.85 | strafe 170 | CoD4-ish |
| `cod_sprintTime` | 8.0 s | full bar duration | Phase 5b (2× initial CoD4 4s) |
| `cod_sprintRechargeTime` | 5.0 s | empty → full | CoD4-like fast regen (vanilla ~20–40 s) |
| `cod_sprintMinTime` | 1.0 s | needed to start a sprint | CoD4 |
| `cod_sprintForwardOnly` | 1 | sprint needs `forwardmove > 0` | CoD4 |
| `cod_sprintLinear` | 1 | single-rate recharge (no 25%/idle bonus) | Phase 5b |
| `cod_sprintRechargeDelay` | 600 ms | pause after sprint before recharge | Phase 5b / CoD-ish |
| `cod_vitalsEnable` | 1 | health regen + linear stamina + bar HUD draw | Phase 5b |
| `cod_maxHealth` | 50 | player max HP (packs clamp here too) | Phase 5b / 5d |
| `cod_flashlightEnable` | 1 | player view flashlight | Phase 5d |
| `cod_flashlightIntensity` | 500 | scales spot beam reach (forced even if `r_dynamiclight 0`) | Phase 5d |
| `cod_flashlightMinDist` | 48 | unused (menu leftover; spots don't use close-wall curve) | Phase 5d |
| `cod_pistolNextShot` | 200 | pistol min ms between shots (vanilla 400) | Phase 5 / 5d tune |
| `cod_flashlightR/G/B` | 1 / 0.95 / 0.85 | warm white | Phase 5d |
| `r_dlightMode` | 1 | rend2 ForwardDlight (needed for spot cones); latch | Phase 5d |
| `cl_renderer` | `rend2` | modern renderer; latch | Graphics |
| `r_ssao` | 1 | screen-space AO; latch | Graphics |
| `r_ext_framebuffer_multisample` | 2 | MSAA 2×; latch | Graphics |
| `r_ext_texture_filter_anisotropic` | 16 | AF; latch | Graphics |
| `r_hdr` / `r_postProcess` / `r_toneMap` / `r_autoExposure` | 1 | HDR tonemap path | Graphics |
| `r_floatLightmap` | 1 | float lightmaps (less banding); latch | Graphics |
| `r_specularMapping` / `r_deluxeMapping` | 1 | specular + deluxe; auto `_s` if present; latch | Graphics |
| `r_forceSun` | 1 | force cascaded sun shadows (stock `q3map_sun`) | Graphics |
| `r_drawSunRays` | 1 | sun god rays; latch | Graphics |
| `r_sunShadows` / `r_sunlightMode` | 1 / 1 | sun CSM plumbing; latch | Graphics |
| `r_shadowFilter` / `r_shadowMapSize` | 2 / 2048 | soft + hi-res cascades; latch | Graphics |
| `cod_healthRegenDelay` | 5000 ms | after last damage before regen | CoD4 |
| `cod_healthRegenRate` | 20 HP/s | linear refill to max | Phase 5b SP feel |
| `cod_ammoScale` | 2 | × ammo pickups/grants + max carry (player) | Phase 5b |
| `cod_interactHint` | 1 | “Press \<key\> to interact” on door/use hints | Phase 5b |
| `cod_hudEnable` | 1 | CoD HUD presentation (ammo style, no bars, low-HP blood/crosshair) | Phase 5c |
| `cod_hudAmmoStyle` | 1 | `1` = `clip/reserve`; `0` = split vanilla | Phase 5c |
| `cod_hudHeatColor` | 1 | ammo text white→red by weapon heat | Phase 5c |
| `cod_hudHealthCrosshair` | 1 | crosshair white→red by missing health | Phase 5c |
| `cod_hudLowHealthBlood` | 1 | persistent bloody screen when low HP | Phase 5c |
| `cod_hudLowHealthStart` | 0.4 | overlay starts at this health/max fraction | Phase 5c |
| `cod_hudLowHealthMaxAlpha` | 0.55 | max overlay opacity near death | Phase 5c |
| `cod_crosshairStyle` | 1 | `1` = CoD 4-post bloom; `0` = vanilla shader | Phase 5c |
| `cod_crosshairGap` | 4 | base half-gap (640) | Phase 5c |
| `cod_crosshairLength` / `Width` | 8 / 2 | post size | Phase 5c |
| `cod_crosshairDot` | 1 | hip-fire center dot | Phase 5c |
| `cod_crosshairBloom` | 16 | extra gap from `aimSpreadScale` | Phase 5c |
| `cod_crosshairMoveBloom` | 14 | extra gap at sprint speed | Phase 5c |
| `cod_crosshairCrouchScale` | 0.55 | gap × while crouching | Phase 5c |
| `cod_crosshairSprintAlpha` | 0.35 | post alpha while sprinting | Phase 5c |
| `cod_crosshairOutline` | 1 | black outline for contrast | Phase 5c |
| `cod_hitMarkerEnable` | 1 | X flash + ticks on enemy hits | E9 |
| `cod_hitMarkerTime` | 250 ms | how long the X stays | E9 |
| `cod_hitMarkerGap` / `Length` / `Width` | 6 / 7 / 2 | X geometry (640 coords) | E9 |
| `cod_hitMarkerSound` | 1 | body vs headshot tick WAVs | E9 |
| `cod_duckTime` | 160 ms | view lerp | slower than the old 70 ms snap; between vanilla 100 and a heavy crouch |
| `cod_duckEase` | 1 | ease-out curve instead of linear | snappier start, soft landing |
| `cod_leanMax` | 32 | offset | slightly further peek |
| `cod_leanRollScale` | 0.6 | roll = leanf × 0.6 → ~19° | "increase camera tilt" |
| `cod_leanTimeIn` | 200 ms | vs 280 | faster peek |
| `cod_leanTimeOut` | 180 ms | vs 350 | much faster return to center |
| `cod_leanAllowFire` | 1 | can shoot while leaned | CoD4 |
| `cod_adsMoveScale` | 0.55 | ADS jog 110 | CoD4-ish |
| `cod_adsFovScale` | 0.8 | 90 → 72 | ~1.25× zoom, per-weapon override |
| `cod_adsTimeIn` / `cod_adsTimeOut` | 220 / 180 ms | | per-weapon override |
| `cod_adsSpreadScale` | 0.35 | spread multiplier at full ADS | hip-fire vs ADS contrast |
| `cod_hipSpreadMin` | 0.55 | floor on aimSpreadScale while hip-firing (0 = off) | CoD cone of fire |
| `cod_hipSpreadScale` | 1 | extra hip multiplier after the floor | tune wildness |
| `cod_semiAutoClick` | 1 | pistols/bolt/semi need release between shots; autos hold-spray | CoD fire modes |
| `cod_adsSensScale` | 1 | sensitivity × (adsFov / baseFov) × this | consistent feel |
| `cod_slideBoost` | 60 u/s | added at slide start | |
| `cod_slideMaxSpeed` | 380 | cap after boost | |
| `cod_slideTime` | 1200 ms | linear decay duration (brief: 1.0–1.5 s) | |
| `cod_slideEndSpeed` | 130 | decays to crouch speed | smooth hand-off to crouch |
| `cod_slideMinSpeed` | 260 | min horizontal speed to start | must really be sprinting |
| `cod_slideCooldown` | 600 ms | | stop slide-spam |
| `cod_aiSpeedMode` | 1 | human AI: run 200, walk 90, crouch 130 | user request: soldiers move like the player (phase 2.4) |
| `cod_slideSteer` | 0.15 | 0 = locked direction, 1 = full air-control-like steering | |
| `cod_proneScale` | 0.15 | prone crawl 30 | CoD4 (ET 0.21) |
| `cod_proneViewHeight` | −8 | eye 16 above feet | ET; CoD4 ≈ 12 scaled |
| `cod_proneMaxsZ` | 16 | prone box top = crouch box top | ET; lower only if stand-up traces stay safe |
| `cod_proneDownTime` / `cod_proneUpTime` | 350 / 350 ms | view ease + move/fire lock | ET 500 ms × 0.7 (brief: ~30% faster) |
| `cod_proneCooldown` | 400 ms | | ET gates toggles at 750 ms |
| `cod_pronePitchUp` / `cod_pronePitchDown` | 40° / 40° | | ET ±40 |
| `cod_proneSpreadScale` | 0.5 | spread multiplier when still and prone | stacks with ADS |
| `cod_proneCrawlFire` / `cod_proneCrawlADS` | 0 / 0 | | CoD4 lowers the gun while crawling |

All prone cvars are listed in [phase-6b-prone.md](phase-6b-prone.md). Gait/bob/sprint-gun cvars are in [phase-4-gait.md](phase-4-gait.md). Feel (jump/inertia/fire) cvars are in [phase-5-feel.md](phase-5-feel.md). Health regen / vital HUD / stamina-finish cvars are in [phase-5b-vitals.md](phase-5b-vitals.md). CoD on-screen HUD cvars are in [phase-5c-hud.md](phase-5c-hud.md).

These are **starting points**. The user tunes them in-game. The final values get written back
here and into the defaults table in `bg_cod.c`.
