# Architecture & Cross-Cutting Rules

Everything here applies to phases 2–5b. Line numbers refer to ioRTCW commit `438e7d4`
(`iortcw/SP/code/...`). They will drift as we edit, so **always re-grep** before patching.

## 1. Codebase map (SP only — ignore `iortcw/MP/`)

| Area | Path | Built into | Notes |
|---|---|---|---|
| Shared "both games" code | `game/bg_*.c`, `game/bg_public.h` | **qagame AND cgame** (compiled twice, see `SP/Makefile` `Q3GOBJ_` ~L2561 and `Q3CGOBJ_` ~L2506) | Player physics (`bg_pmove.c`), slide/step (`bg_slidemove.c`), anims, item tables |
| Server game | `game/g_*.c`, `game/ai_*.c` | `qagame.sp.x86_64.so` | Spawning, `ClientThink_real`, weapons firing, AI, savegames |
| Client game | `cgame/cg_*.c` | `cgame.sp.x86_64.so` | View, FOV, viewmodel, HUD, prediction |
| UI | `ui/` | `ui.sp.x86_64.so` | Menus (we only touch this if we add menu options, not planned) |
| Engine | `client/`, `qcommon/`, `server/`, `sys/`, `renderer*/` | `iowolfsp.x86_64` | Input buttons, network encoding, file system. **Avoid changes** unless a phase explicitly needs it |

### Key functions

| Function | File:line | Role |
|---|---|---|
| `PmoveSingle` | `game/bg_pmove.c:4013` | Per-command movement driver. Order: viewangles → `PM_CheckDuck` → `PM_GroundTrace` → move type (`PM_WalkMove`/`PM_AirMove`/…) → `PM_Sprint` → `PM_Animate` → `PM_Weapon` → `PM_Footsteps` |
| `PM_CmdScale` | `bg_pmove.c:381` | Turns input into speed: `ps->speed * (sprint ? sprintSpeedScale : runSpeedScale)` |
| `PM_WalkMove` | `bg_pmove.c:900` | Ground movement; crouch speed clamp at ~L1001 (`ps->speed * crouchSpeedScale`) |
| `PM_Friction` / `PM_Accelerate` | `bg_pmove.c:246 / 323` | Friction & acceleration (`pm_friction`, `pm_accelerate` globals near top of file) |
| `PM_CheckDuck` | `bg_pmove.c:1607` | Sets `PMF_DUCKED`, bbox, **instant** `viewheight` change |
| `PM_Sprint` | `bg_pmove.c:3948` | Stamina (`ps->sprintTime`, 0..20000). Drains **50 per call** (frame-rate dependent; see phase 2) |
| `PM_UpdateLean` | `bg_pmove.c:3576` | Lean offset `ps->leanf`; constants `LEAN_MAX 28`, `LEAN_TIME_TO 280`, `LEAN_TIME_FR 350` at L3566 |
| `PM_Weapon` | `bg_pmove.c:2726` | Firing, reload, weapon switch. Blocks fire while leaning (~L3098) |
| `PM_AdjustAimSpreadScale` | `bg_pmove.c:2550` | Spread 0..255 (`ps->aimSpreadScale`) |
| `ClientSpawn` speed scales | `game/g_client.c:~1799` | `runSpeedScale 0.8`, `sprintSpeedScale 1.1`, `crouchSpeedScale 0.25`, view heights |
| `ClientThink_real` speed | `game/g_active.c:~1002` | `client->ps.speed = g_speed.value` (**runs for AI too**) |
| Bullet spread | `game/g_weapon.c:~1660-1725` | Uses `client->currentAimSpreadScale` |
| `CG_OffsetFirstPersonView` | `cgame/cg_view.c:536` | Duck smoothing (`DUCK_TIME 100`, `cg_local.h:57`), lean camera roll `leanf/2` and offset (~L666) |
| `CG_CalcFov` | `cgame/cg_view.c:786` | FOV, binocular/scope zoom, `cg.zoomSensitivity` |
| `CG_CalculateWeaponPosition` | `cgame/cg_weapons.c:1712` | Viewmodel lean, bob, land-dip, idle drift |
| `CG_AddViewWeapon` | `cgame/cg_weapons.c:2934` | Final viewmodel origin = position + `cg_gunX/Y/Z` + fov offset |
| `CG_DrawCrosshair` | `cgame/cg_draw.c:2347` | Crosshair (already hidden while leaning) |
| `CG_PredictPlayerState` | `cgame/cg_predict.c:520` | Client prediction; `cg_showmiss 1` prints prediction errors |
| Input buttons | `client/cl_input.c:~260-280, 1056-1076` | `+sprint`, `+attack2`, `+zoom`, `+leanleft/right`, spare `+wbutton6`, `+wbutton7` |

## 2. How a movement frame flows

```
Engine input (cl_input.c) → usercmd_t {forwardmove, rightmove, upmove, buttons, wbuttons}
        │
        ├─► SERVER (qagame): ClientThink_real (g_active.c) → sets ps.speed → Pmove(ps, cmd)
        │       authoritative result → snapshot → network → client
        │
        └─► CLIENT (cgame): CG_PredictPlayerState → Pmove(copy of ps, same cmds)
                predicted result drawn immediately; corrected when snapshot arrives
```

In SP both run in the same process, but they are still two separately compiled modules
with **separate globals**. When they disagree, you see jitter or "prediction miss".

## 3. The three golden rules

### Rule 1 — Gate everything on the player, not on AI
`Pmove` runs for every AI character (`ps->aiChar != 0`). The AI tunes its own speed scales
(`ai_cast_think.c:652`, `ai_cast_characters.c:1464`) and its navigation assumes vanilla
physics. **Every** new behaviour in `bg_pmove.c` must start with:

```c
if ( pm->ps->aiChar ) { /* vanilla path */ }
```

Never change `g_speed` (it is applied to AI clients too). Override the player's
`ps.speed`/scales only where `!client->ps.aiChar`.

**One deliberate exception:** phase 2.4 (`cod_aiSpeedMode`) changes human AI walk/run/crouch
*speed values* in the server-only AI think code (`ai_cast_think.c`). It never touches
`bg_pmove.c` or AI behaviour, and `cod_aiSpeedMode 0` restores vanilla.

### Rule 2 — New pmove state must be networked
The client only gets the playerState fields listed in `qcommon/msg.c` `playerStateFields[]`
(~L1327) plus `stats[]`, `persistant[]`, `powerups[]`, `ammo`. Fields under the
"not communicated over the net" comment in `playerState_t` (e.g. `sprintExertTime`,
`jumpTime`, `quickGrenTime`) are **not** networked. If prediction uses them, it will drift.

Free, networked slots verified at `438e7d4`:

| Slot | Type / range | Planned use |
|---|---|---|
| `pm_flags` bit `128` | 16-bit flags. 128 is the only unused bit (verify with grep) | `PMF_COD_SLIDING` (phase 4) |
| `stats[8]` | `short` (−32768..32767) | `STAT_COD_ADS` — ADS fraction ×1000 (phase 3) |
| `stats[9]` | `short` | `STAT_COD_SLIDE` — >0 slide ms remaining, <0 cooldown ms (phase 4) |
| `stats[10]` | `short` (use as 15-bit flags) | `STAT_COD_FLAGS`: `COD_SF_SPRINTING` (phase 2); `COD_SF_PRONE`, `COD_SF_PRONE_MOVING`, `COD_SF_PRONE_HELD`, `COD_SF_CROUCH_HELD` (phase 5b) |
| `stats[11]` | `short` | `STAT_COD_SLIDE_SPEED`: start speed of the current slide, u/s (phase 4) |
| `stats[12]` | `short` | `STAT_COD_STANCE`: >0 prone transition ms left, <0 prone cooldown ms (phase 5b) |
| `stats[13..15]` | `short` | spare |

Add the `STAT_COD_*` names to the `statIndex_t` enum in `game/bg_public.h` (after
`STAT_PLAYER_CLASS`), and add a compile-time check that the enum stays `<= MAX_STATS`.

**Do not add fields to `playerState_t`.** That needs engine `msg.c` changes, breaks
demo/savegame compatibility, and isn't needed.

### Rule 3 — Deterministic, time-based math
- Use `pml.msec` / `pml.frametime` for every rate. Never count per call or per frame.
- `bg_pmove.c` must read **identical** tuning values in qagame and cgame (see §5).
- Don't call `rand()`/`crandom()` in pmove for things that affect movement.

## 4. Input

| Action | Command | usercmd bit | Default key (mod cfg) |
|---|---|---|---|
| ADS (hold) | `+wbutton6` (alias `+ads`) | `wbuttons & WBUTTON_EXTRA6` → `#define WBUTTON_COD_ADS WBUTTON_EXTRA6` | `MOUSE2` |
| Sprint | `+sprint` | `buttons & BUTTON_SPRINT` | `SHIFT` |
| Crouch (toggle, phase 5d) | `togglecrouch` → sticky `+movedown`/`-movedown` | `cmd.upmove < 0` | `c` (hold still available via `bind c +movedown`) |
| Jump | `+moveup` | `cmd.upmove > 0` | `SPACE` (vanilla also had `MOUSE2`, which becomes ADS) |
| Fire | `+attack` | `buttons & BUTTON_ATTACK` | `MOUSE1` only (`unbind CTRL` in `codmod.cfg`; vanilla also had `CTRL=+attack`) |
| Lean | `+leanleft`/`+leanright` | `WBUTTON_LEANLEFT/RIGHT` | `q` / `e` |
| Alt weapon mode | `weapalt` | (cgame command) | `MOUSE3`, `z` |
| Quick knife | `quickknife` | (cgame command) | `v` |
| Flashlight (phase 5d) | `toggleflashlight` | eye-origin rend2 spot cones (`AddSpotLightToScene`, `REF_SHADOW_DLIGHT` → shadow map, `r_flashlightShadow`) | `l` |
| Prone (toggle, phase 6b) | `+wbutton7` (alias `+prone`) | `wbuttons & WBUTTON_EXTRA7` → `#define WBUTTON_COD_PRONE WBUTTON_EXTRA7` | `CTRL` |

`wbuttons` is delta-encoded as 8 bits (`msg.c` ~L674), so bit 64 travels to the server.
`WBUTTON_EXTRA6/7` are unused by game code at `438e7d4` (verify with grep).
`+ads`/`-ads` are registered in the engine as aliases for `+wbutton6` (ioRTCW SP has no
console `alias`). Binds live in `mod/codmod/codmod_binds.cfg`, which does a **full** reset
(`unbindall` → `exec default.cfg` → codmod deltas) on first launch, `--reset-binds` (alias `--reset-settings`), menu
Defaults/RESET SETTINGS (when `fs_game` is `codmod`), or `/cod_resetbinds` (phase 5d):

```
// codmod_binds.cfg (full reset)
unbindall
exec default.cfg
bind MOUSE2 "+ads"
unbind CTRL                 // prone in phase 6b
bind v "quickknife"
bind f "+activate"
bind c "togglecrouch"
bind l "toggleflashlight"
```
Vanilla defaults worth knowing (from `pak0.pk3` `default.cfg`): `g`/`x` = `+kick`,
`f`/`ENTER` = `+activate`, `r` = reload, `b` = binoculars, `n` = notebook, `CAPSLOCK` = walk.

## 5. Tuning cvars (`cod_*`)

### Design
New shared files **`game/bg_cod.h` / `game/bg_cod.c`** (add `bg_cod.o` to **both** `Q3GOBJ_`
and `Q3CGOBJ_` in `SP/Makefile`, following the `bg_pmove.o` lines):

```c
// bg_cod.h
typedef struct {
	int   enable;               // master switch: 0 = vanilla behaviour everywhere
	float runSpeed;             // u/s, player jog
	float sprintScale;          // × runSpeed
	float walkScale;            // × runSpeed when BUTTON_WALKING
	float crouchScale;          // × runSpeed
	float backScale, strafeScale;
	// ... per-phase fields, see phase docs
} codTuning_t;

extern codTuning_t bg_cod;          // one instance per module (qagame & cgame each have one)

typedef struct { const char *name; const char *def; int flags; size_t ofs; int isInt; } codCvarDef_t;
extern const codCvarDef_t bg_codCvars[];   // single source of truth: name, default, offset into codTuning_t
extern const int bg_numCodCvars;
```

- **One table, two registrars.** `g_main.c` (`G_RegisterCvars`/`G_UpdateCvars` ~L1017) and
  `cg_main.c` (`CG_RegisterCvars`/`CG_UpdateCvars` ~L537) each loop over `bg_codCvars`,
  keep a local `vmCvar_t` array, and copy values into `bg_cod` every frame. Both modules
  share one cvar system (same process), so values match automatically.
- **Flags:** `0` for tunables (not archived, so code defaults always apply; user overrides go
  in `codmod.cfg`). `CVAR_ARCHIVE` only for user preferences (e.g. `cod_debugHud`,
  `cod_menuScale`).
- **Dump command:** cgame command `cod_dump` prints `seta cod_xxx "value"` for every entry, so
  a tuned feel can be pasted into `codmod.cfg` or back into the defaults table.
- **Per-feature enables:** `cod_enable` (master) plus one per feature (`cod_moveEnable`,
  `cod_leanEnable`, `cod_adsEnable`, `cod_slideEnable`, `cod_proneEnable`). Each check is
  `bg_cod.enable && bg_cod.xxxEnable`. This gives instant A/B comparison with vanilla.

## 6. Debug HUD (built in Phase 2, extended in 3–5c)

New file `cgame/cg_cod.c` (add to `Q3CGOBJ_`). Hook its draw function from the 2D draw
path in `cg_draw.c` (near where `cg_drawFPS` is drawn). `cod_debugHud 1` shows, top-left, small text:

`/cod_menu` opens a sectioned right-side tune overlay (`cgame/cg_cod_menu.c`) for every
`cod_*` cvar; `cod_menuScale` (archived) sizes the text/panel. Dumps append to
`codmod_tune.log` under `fs_homepath`. In-game console commands need a leading `/`.

```
spd 201.4 u/s  (h-vel)   state RUN|WALK|SPRINT|CROUCH|PRONE|CRAWL|SLIDE|AIR
stam 15230/20000         viewh 40  duck-lerp 0.63
lean  -17.2/32           ads 0.84  fov 74.1
slide 612 ms             cooldown 0
stance 0 ms (prone transition >0, cooldown <0)
```

Horizontal speed = `sqrt(vx²+vy²)` of `cg.predictedPlayerState.velocity`. This HUD is how
we verify numbers against [reference-values.md](reference-values.md) and how the user
reports tuning.

## 7. Savegames

`game/g_save.c` saves `ps.stats[]` (L221) and `ps.persistant[]`, but not `pm_flags`.
After loading:
- `STAT_COD_ADS` may come back non-zero, which is harmless because it lerps to the current input.
- `STAT_COD_SLIDE` may be non-zero without `PMF_COD_SLIDING`. Treat that as "not sliding"
  (clamp positive values to 0 if the flag is absent).
- Prone (5b): `COD_SF_PRONE` is in `stats[]`, so it survives a load even though `pm_flags`
  (`PMF_DUCKED`) doesn't. `PM_CodCheckProne` re-applies the prone box, view height and
  `PMF_DUCKED` from the flag on the first frame. Clamp a positive `STAT_COD_STANCE` to 0 on load.
- Speed scales: re-apply the player's CoD scales every frame in `ClientThink_real` (not
  only in `ClientSpawn`), so loading an old save or changing cvars takes effect at once.

The mod uses its own `fs_game` dir, so its saves live in `run/home/codmod/save/`, apart
from vanilla saves.

## 8. Code conventions

- Match id/Gray Matter style: tabs, `if ( x ) {`, spaces inside parens, `qboolean`.
- Tag every change: `// codmod: <short why>`. For larger replaced blocks, keep the original
  under `#if 0 // codmod: original` only when it helps review. Otherwise delete it.
- New logic goes in new functions (`PM_CodXxx`) and new files where practical, keeping the diff
  in vanilla files small. That makes upstream rebases easier.
- Never edit the bundled third-party libs (`code/SDL2`, `zlib`, `jpeg`, …).
- GCC 16 prints warnings from vendor code. Don't "fix" them. New code must compile without
  new warnings.
- `g_func_decs.h` / `g_funcs.h` are generated tables of think and use function pointers, for
  savegames. We add **no** new entity think functions, so they stay untouched. If that ever
  changes, both files must be updated by hand.
