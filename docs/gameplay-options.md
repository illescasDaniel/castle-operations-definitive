# Gameplay options (MODS > GAMEPLAY)

Eleven on/off toggles that switch the mod's mechanics back to original RTCW. Menu: `mod/codmod/ui/gameplay.menu`
(codmod layer, opened by the GAMEPLAY button in `mods.menu`, so main menu only).

Each toggle is an archived cvar `cod_opt*` (`bg_cod.c` table, code default 0 = vanilla; `codmod_defaults.cfg`
`seta`s them to 1, so saved choices persist and menu Reset restores them). `BG_CodApplyOptions()` (bg_cod.c) runs at the
end of every `BG_CodUpdateCvars()` in qagame and cgame and clears the feature flags a group owns, so the existing
`bg_cod.xxxEnable` checks keep working and prediction matches the server.

| Cvar | Menu row | Clears when 0 |
|---|---|---|
| `cod_optMovement` | Movement | moveEnable, leanEnable, landSlowEnable, gaitEnable, duck smoothing back to 100 ms linear |
| `cod_optSlide` | Slide | slideEnable (also off when Movement is off: sliding starts from the CoD sprint flag) |
| `cod_optProne` | Prone | proneEnable |
| `cod_optAiming` | Aim Down Sights | adsEnable (ADS + hipfire cone), adsSwayEnable, crosshairStyle |
| `cod_optRecoil` | Weapon Recoil | recoilEnable |
| `cod_optWeapon` | Weapon Handling | weaponEnable (click-fire, fire-rate overrides), quickKnifeEnable, kickDamage 15 |
| `cod_optRegen` | Health Regeneration | healthRegenEnable, maxHealth 0 (player keeps RTCW's 100); the horizontal health bar (hud.menu) is drawn only while this is 0 |
| `cod_optStamina` | Stamina Changes | `staminaEnable`: PM_Sprint falls back to RTCW's per-call drain/recharge; the horizontal stamina bar is drawn only while this is 0 |
| `cod_optAmmo` | More Ammo | ammoScale 1 |
| `cod_optHitMarkers` | Hit Markers | hitMarkerEnable |
| `cod_optEnemy` | Fast Enemies | aiSpeedMode 0, aiSprint 0 |
| `cod_optTactics` | Tactical Enemies | aiTactics 0 (vanilla AI fight functions run; applies live on the next think) |

Notes: health and enemy-speed changes apply on the next map load (max health is set at spawn, AI speeds when the
actor spawns). `cod_*` tuning values (speeds, scales) are unchanged; they stay in `codmod_tuning.cfg`.
Not toggled (always on): CoD HUD layout, flashlight (own setting in the game menu), menus, graphics.

In-game text must not name the commercial game it imitates: menu labels say "modern"/"boosted", never CoD.
