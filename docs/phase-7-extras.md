# Phase 7 — Optional Extras (only on user request)

Backlog of CoD4-feel improvements outside the core phases. Each is independent.
Ask the user which ones they want before starting any.

| # | Feature | Notes / approach | Effort |
|---|---|---|---|
| E1 | ~~Sprint weapon-lower + fire rules~~ | Moved into [phase-4-gait.md](phase-4-gait.md) | — |
| E2 | ~~Toggle ADS~~ | Moved into phase 3.1: cfg-only `toggleads` alias, no engine change | — |
| E3 | ~~Scoped weapons on right-click~~ | Moved into phase 3.8 (hold-to-scope) | — |
| E4 | **ADS sway / breath** | Built 2026-10-13, awaiting playtest: viewmodel-only breathing sway (two slow sines on pitch/yaw) scaled by ADS fraction, movement speed, crouch/prone. Defaults pitch 0.34 / yaw 0.22 (tuned down 2026-10-13). Cvars `cod_adsSway{Enable,Pitch,Yaw,Rate,Move,Crouch,Prone}` (`/cod_menu` > ADS). Code: `CG_CalculateWeaponPosition` | S |
| E5 | **Recoil model** | Done 2026-10-13, user approved feel: real aim kick per shot in `PM_Weapon` (`PM_CodRecoilKick` moves `ps->delta_angles`, player only; per-weapon degrees table in code), unrecovered climb in `STAT_COD_RECOIL`; pulling down cancels it, rest recovers after `cod_recoilDelay` at `cod_recoilRecover` deg/s; `CG_CodRecoilSmooth` eases the snap in cgame; old cosmetic kick disabled. Cvars `cod_recoil{Enable,Scale,AdsScale,Crouch,Prone,Recover,Delay,Max}` (`/cod_menu` > RECOIL). Original idea: CoD-style view kick: per-weapon pitch/yaw kick with recovery, less while ADS (`CG_KickAngles` in `cg_view.c:363`, plus the server-side spread). Bigger gunplay change | M |
| E6 | ~~Landing slowdown~~ | Promoted to [phase-5-feel.md](phase-5-feel.md) | — |
| E7 | ~~Jump tuning~~ | Promoted to [phase-5-feel.md](phase-5-feel.md) (`cod_jumpVelocity`) | — |
| E17 | ~~Ground inertia / accel-friction~~ | Promoted to [phase-5-feel.md](phase-5-feel.md) | — |
| E18 | ~~Pistol / semi tap-fire~~ | Promoted to [phase-5-feel.md](phase-5-feel.md) (SP nextShotTime 400→click-responsive) | — |
| E19 | ~~Quick knife (V)~~ | Promoted to [phase-5-feel.md](phase-5-feel.md) §5.5 — cgame `quickknife`, not `+kick` | — |
| E20 | ~~Health regen / vital HUD~~ | Promoted to [phase-5b-vitals.md](phase-5b-vitals.md) — CoD regen, stamina finish, horizontal bars | — |
| E21 | ~~CoD on-screen HUD~~ | Promoted to [phase-5c-hud.md](phase-5c-hud.md) — `clip/reserve` ammo, no health/stamina bars, low-HP blood | — |
| E8 | ~~Prone~~ | Promoted to its own phase: [phase-6b-prone.md](phase-6b-prone.md) (ET code port + optional ET animation retarget) | — |
| E9 | ~~**Hit markers**~~ | Done 2026-10-09: SP bumps `PERS_HITS` (+ `PERS_GAUNTLET_FRAG_COUNT` for headshots); cgame draws a short X around the crosshair and plays body/headshot ticks from `codmod_fx.pk3`. Cvars `cod_hitMarker*`; `/cod_menu` → **HIT MARKER** | — |
| E10 | **Menu options** | Expose key `cod_*` cvars in the UI menus (`ui/` + menu files in a `zz_codmod.pk3`) | M |
| E11 | **Packaging** | `zz_codmod.pk3` for cfg and menu assets, plus a tarball of `run/codmod` + engine for sharing. Never include `zz_codmod_etanims.pk3` (ET assets) | S |
| E13 | **AI sprint** | Done 2026-10-13, user approved: server-only timed burst (`AICast_CodTrySprint` / `AICast_CodSprintMul` in `ai_cast_think.c`; state in static arrays so the savegame layout is unchanged). Triggers: `AIFunc_BattleChase` when the target is farther than `cod_aiSprintMinDist` (350) and `AIFunc_BattleTakeCoverStart` when cover is >200 away. Cvars `cod_aiSprint` (1), `cod_aiSprintScale` (1.5), `cod_aiSprintTime` (2500 ms), `cod_aiSprintCooldown` (4000 ms). Human AI only, never during scripted events/walk/crouch; `cod_aiSprint 0` = vanilla. Original idea: Human soldiers sprint (×1.5 for a few seconds) when charging, chasing, or running to cover. Needs AI behaviour hooks (`ai_cast_funcs.c` battle-chase ~L2971 already has a "chase accel" window) plus a speed boost in `ai_cast_think.c`. Check scripted sequences | M |
| E12 | **Hold-crouch-to-prone** | CoD4 option: holding crouch for ~0.4 s goes prone. Pmove timer in `STAT_COD_STANCE` | S |
| E14 | **Higher menu resolutions** | In-game video menu can't pick modes like 2560×1600. Extend the r_mode / custom-resolution UI (and/or mode list) so native high-DPI modes are selectable without console `r_mode -1` + `r_customwidth/height` | S |
| E15 | **Mouse sensitivity as a number box** | Replace (or supplement) the in-game sensitivity slider with a text field for exact values (fine tuning below slider steps) | S |
| E16 | **FOV slider** | Add an in-game FOV control if none exists (or expose `cg_fov` in the options menu). Defaults stay vanilla until the user changes them | S |
| E22 | **HD textures (2× AI)** | Local uv tool [`tools/hd-textures`](../tools/hd-textures/README.md): pilot A/B → full SP batch → gitignored `codmod_hd.pk3`. Share the script only; never redistribute upscaled proprietary art. Needs `r_picmip 0` / `r_picmip2 0`. Branch/worktree: `hd-textures` | M |
| E23 | **HD audio (AI remaster)** | Local uv tool [`tools/hd-audio`](../tools/hd-audio/README.md) + `./remaster.sh`: locked **`sr_only`** (SFX/VO) + music **`sr_linked`** → gitignored `codmod_hd_audio.pk3`. Share the script only; never redistribute remastered proprietary audio. | M |
