# Architecture & Cross-Cutting Rules

Everything here applies to phases 2–5b. Line numbers refer to ioRTCW commit `438e7d4`
(`iortcw/SP/code/...`). They will drift as we edit, so **always re-grep** before patching.

## 0. Engine fork vs mod folder: who does what

Measured 2026-10-18 from the fork's diff against upstream ioRTCW (`438e7d4` to HEAD): 120 files, +31,305 / -663 lines.
About 15k of those lines are the generated SMAA lookup table (`rend2/smaa_areatex.h`), not hand-written code.

**Short version:** nearly all behavior (mechanics, HUD, renderer features, input, menus' code) is C code in the
`iortcw` fork. `mod/codmod/` holds configuration and content only; nothing in it is compiled.

### What upstream ioRTCW is (not ours)
A modernized RTCW source port: 64-bit builds, SDL2, OpenAL, the `rend2` renderer, platform and bug fixes. On its own it
plays vanilla RTCW.

### What the iortcw fork adds

| Area | Lines changed | What it does |
|---|---|---|
| Renderer (`rend2/`) | ~19.8k (~5k without the SMAA table) | GTAO/SSAO, SMAA, bloom and colour grade; per-pixel dynamic lights on models, specular, flashlight shadow map; GPU pass profiler; no per-frame `glFinish`, occlusion-query flares (bench 183 to 303 FPS) |
| cgame (`cgame/`) | ~4.7k | `cg_cod.c` (ADS view, gait/bob, recoil, sway, HUD), `cg_cod_menu.c` (`/cod_menu` tuning overlay), `cg_subtitles.c` |
| Shared + server game (`game/`) | ~2.5k | `bg_pmove.c` (CoD speeds, slide, prone, crouch, lean), `bg_cod.c/.h` (~199 `cod_*` cvars), AI sprint and scripted-event AI speeds, health regen |
| UI (`ui/`) | ~1.9k | `ui_shared.c`, `ui_main.c`, `ui_lang.c` (multi-language), menu fixes (cursor, popups, save list) |
| client / sdl / qcommon | ~2.6k | Gamepad and gyro input, MJPEG/AVI cutscene playback, FPS pacer and limiter, `cod_skipIntro`, soft `vid_restart` |

### What the outer repo and `mod/codmod/` hold (no compiled code)

| Item | Role |
|---|---|
| `codmod_defaults.cfg` | First-launch and Reset values of user-facing settings (`seta`); execs the binds and the graphics subset |
| `codmod.cfg` | Pinned internal values (`set`), run every launch; execs `codmod_tuning.cfg` |
| `codmod_tuning.cfg` | Every `cod_*` tuning value (the source of truth) |
| `codmod_binds.cfg` | Key binds only (keyboard and CoD4 pad) |
| `codmod_gfxdefaults.cfg` | Recommended GRAPHICS > ADVANCED values (also run by the "restore recommended" button) |
| `menu-deltas/*.delta` (30) | Patches applied to RTCW's own menus (generated `.menu` files are never committed) |
| `lang/de`, `lang/es` | Translated strings; subtitles are built by `tools/subtitles` |
| `codmod_fx.pk3`, `codmod_pad.pk3`, `ui/` assets | Hitmarker sounds, gamepad glyphs, menu cursor |
| `scripts/` | Build, install, run, menu build, screenshot diff |
| `tools/` | Local AI pipelines (`hd-textures`, `hd-audio`, `hd-video`), `l10n`, `subtitles`, `spec-bake`; their pk3 outputs are generated per user and stay private |
| `docs/`, `memory/` | Plan, phase docs, project state |

The original game `.pk3` data is never modified or copied; the Steam install is only symlinked.

### How the mod switches features on
The engine fork defaults to vanilla RTCW: `cod_enable 0`, renderer features off (`r_bloom`, `r_grade`, `r_ao`, `r_aa`,
`r_codSpecular`, dynamic light and flashlight shadow cvars), `s_alHRTF 0`, `cod_subtitles 0`. Each feature is a cvar
that a mod can turn on. `codmod` does that through its config files, loaded by the hooks below.

Engine hooks in `Com_ExecuteCfg` (`qcommon/common.c`), used only when `fs_game` is set and not `main`:

```
exec default.cfg                 game's own
exec <fs_game>_defaults.cfg      mod defaults: first launch and Reset; runs before the user config, so saved choices win
exec wolfconfig.cfg              user config
exec autoexec.cfg                user
exec <fs_game>.cfg               mod pinned config: runs after the user config, so it always applies
```

All of this runs before renderer and input init, so latched cvars (`r_codSpecular`, `in_joystick`, ...) apply on the
first boot. A command-line `+set` is applied after all of the above and wins (this is how the bench overrides work).
`execmodcfg` re-runs both mod files; the menu Reset action uses it after `cvar_restart`. `scripts/run.sh` only adds
`+set fs_game codmod` (and `+exec codmod_defaults.cfg` for `--reset-settings`).

`codmod.cfg` pins internal values (for example `r_deluxeSpecular 3`, `r_cubeMapping 1`, `cod_enable 1`) and execs
`codmod_tuning.cfg`. The engine's defaults for user-facing settings are vanilla values; the mod's values
come from `codmod_defaults.cfg`. See `AGENTS.md`, "User settings vs internal config", for the rule.

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
`bg_pmove.c` or AI behaviour, and `cod_aiSpeedMode 0` restores vanilla. It is skipped while the AI runs a
scripted event (cutscenes, scripted walks) so actors keep their authored animation speeds.

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
- **Flags:** `0` for tunables (not archived, so code defaults always apply; codmod's values come
  from `codmod_tuning.cfg`). `CVAR_ARCHIVE` only for user preferences (e.g. `cod_debugHud`,
  `cod_menuScale`).
- **Dump command:** cgame command `cod_dump` prints `seta cod_xxx "value"` for every entry, so
  a tuned feel can be pasted into `codmod_tuning.cfg` (the source of truth) or back into the defaults table.
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
