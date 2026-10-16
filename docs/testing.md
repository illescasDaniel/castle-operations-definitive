# Testing Guide

There is no automated test harness for game feel. Testing combines **build checks**,
**agent smoke runs**, and **user play-tests** guided by the debug HUD.

## Every change (agent)

1. `scripts/build.sh --game-only --install` (or the full build if engine files changed). `--install` runs
   `scripts/install.sh` afterwards; without it `run/` keeps stale modules and the game ignores your change. It must finish with no
   errors and no *new* warnings in files we touched:
   `make ... 2>&1 | grep -E "warning|error" | grep -E "bg_cod|cg_cod|bg_pmove|cg_view|cg_weapons|g_active|g_weapon"`.
2. (Install is done by `--install` above.)
3. Smoke run (opens a window for ~45 s):
   `timeout 45 scripts/run.sh --windowed 1280x720 +spdevmap escape1 +set cod_debugHud 1`
   Then scan `run/home/codmod/rtcwconsole.log` for `ERROR`, `WARNING: ... cod_`, crashes, and our
   own `codmod` prints. (ioRTCW names the file `rtcwconsole.log`, not `qconsole.log`.)
4. If the agent has screenshot or computer-use access, it can capture a screenshot of the HUD
   to sanity-check the numbers. Otherwise it leaves the in-game verification to the user.

## Safety rules (learned the hard way, 2026-10-11)

An agent's "benchmark" attempt left the game with no HUD and no visible pause menu, then wiped the
user's binds. Rules so it cannot repeat:

1. **HUD/menus are the canary.** Anything touching `rend2/tr_backend.c`, `tr_fbo.c`, `RB_SwapBuffers`,
   `RB_PostProcess`, `cl_scrn.c` or `SCR_DrawScreenField` must be checked **by the user in a real map**
   (HUD visible, ESC pause menu visible) with MSAA on (our default) before it is called done.
   All 2D is drawn *after* post-process; the final present must include it. Never present
   `tr.msaaResolveFbo` straight after post-process.
2. **No automated HUD smoke test.** Tried and dropped: the real flow is main menu → click → cutscene
   before any HUD, so scripted launches don't reach gameplay reliably. Don't rebuild it; the user verifies.
3. **Never wipe or reset the user's `wolfconfig.cfg`** (binds, display, pad prefs). `scripts/run.sh`
   keeps a rolling backup in `run/home/codmod/cfg-backups/` (newest 15) on every launch; restore from
   there. Tools/tests must not add a "reset config" option.
4. **Don't patch symptoms with guardrails.** Forcing cvars every launch or force-closing UI hid the real
   bug. Find the cause (diff the recent engine changes first) before adding workarounds.
5. **Back up before experimenting:** `git stash` only covers one repo. The engine is the separate
   `iortcw/` repo; check `git status` in **both** before concluding "it's not the code".
6. A new debug/benchmark feature must be removable in one step (isolated commit or stash) and must not
   touch the render present path or archived cvars.

## Cutscene lighting (lite mode + `r_cutsceneFx`)

Scripted cams (`cg.cameraMode`, e.g. escape1 intro) set `RDF_NOSUNLIGHT`. Default
`r_cutsceneFx 27` keeps sun/CSM, map dlights, HDR autoexposure, and sun rays; turns off
SSAO/AO; flashlight is skipped in cgame. Filmic exposure (`r_cameraExposure`) matches
gameplay. Gamma default is **`r_gamma 1`**.

| bit | value | feature |
|---|---|---|
| sun/CSM | 1 | `r_forceSun` cascades |
| dlights | 2 | map/scripted dynamic lights |
| AO | 4 | SSAO/GTAO (off by default in cams) |
| autoexposure | 8 | HDR autoexposure |
| sun rays | 16 | `r_drawSunRays` |
| gamma | 32 | keep user `r_gamma` if raised (else HW ramp = 1.0) |

Default is `27` (sun+dlights+autoexp+rays). A/B: `r_cutsceneFx 11` (no rays), `19` (no autoexp), `63` (all incl. AO).
Verify: New Game → escape1 outdoor flags/sky, then normal play.

## Soft vs hard `vid_restart` (MangoHud / overlays)

Under `scripts/game_run.sh` (gamemode + MangoHud `LD_PRELOAD`, SDL Wayland), destroying and recreating
the GL context SIGSEGVs. `CL_Vid_Restart_f` therefore splits:

| Path | When | Behaviour |
|---|---|---|
| FS in-place | Only `r_fullscreen` latched | `IN_ToggleFullscreenInPlace` → `SDL_SetWindowFullscreen`; no restart |
| Soft | Mode / custom size / FBO MSAA / bare `vid_restart` | `re.Shutdown(qfalse)` + `GLimp_SetModeInPlace` + UI/cgame reload; **keeps** window/GL/`renderer.so` |
| Hard | Context attrs: `r_ext_multisample`, `r_colorbits`/`depthbits`/`stencilbits`, `r_stereoEnabled`, `cl_renderer` | Full `CL_ShutdownRef` destroy/recreate (still fragile under MangoHud) |

Smoke (agent): mangohud + mode change should print `vid_restart: soft (keep GL context)` and
`GLimp_SetModeInPlace: … (no GL recreate)`, then exit cleanly — not SIGSEGV.

## Console toolbox

| Command | Use |
|---|---|
| `spdevmap escape1` | Load the first level with cheats |
| `god`, `notarget`, `noclip`, `give all`, `nofatigue` | Test without dying or being bothered |
| `cod_debugHud 1` | Speed / state / stamina / lean / ADS / slide readout |
| `cod_enable 0/1` | Instant A/B against vanilla behaviour |
| `cod_dump` | Print all current `cod_*` values (paste into `codmod.cfg`) |
| `cg_showmiss 1` | Print client prediction errors. **Must stay silent** during our new mechanics |
| `com_maxfps 60` / `125` / `250` | Frame-rate independence checks |
| `timescale 0.25` | Slow motion to inspect transitions (cheat) |
| `cg_thirdPerson 1` | See the player's body / bbox behaviour (cheat) |
| `savegame t1` / `loadgame t1` | Savegame robustness |

## Good test spots

- `escape1` start cell and corridor: flat floors for speed and slide measurements,
  walls for spread groups and the slide-into-wall test, low guards for AI regression checks.
- `escape2` / `village1`: slopes, stairs, crouch gaps, ladders, water.
  (The agent should note exact spots found during testing in this file.)

## Measuring

- Speeds: read the HUD's horizontal speed while holding the input for >1 s. Tolerance ±2%.
- Durations: HUD timers (stamina, slide ms) or `cg_drawTimer`.
- Distances: `viewpos` (or `where`) before and after a slide. Compute the planar distance.
- Spread: 20 shots at a wall from a fixed `setviewpos`, compare hip vs ADS decal spread.

## Regression list (run before each phase report)

- [ ] Vanilla (`scripts/run.sh --vanilla`) still runs: `run/main` modules untouched.
- [ ] `cod_enable 0` feels like vanilla.
- [ ] AI patrol, chase, crouch, and shoot behaviour unchanged in the first 2–3 minutes of `escape1`
      (with `cod_aiSpeedMode 0`; with mode 1 only the speeds differ).
- [ ] Save and load mid-level works.
- [ ] No `cg_showmiss` spam.
- [ ] Ladders, swimming, MG42 mounting, binoculars, sniper scope, and weapon alt-modes still work.
- [ ] (after 4b) Prone in/out, crawl speed, and a stand-up under an overhang still work. `cod_proneEnable 0` restores vanilla stance.
