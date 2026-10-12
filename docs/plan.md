# RTCW remaster (`codmod`) — Master Plan

> **Audience:** an execution agent (or human) implementing this mod.
> **Status:** gameplay phases largely shipped; remaster presentation (HD textures/audio, menus) ongoing.
> **Kick-off prompt for the execution agent:** [execution-prompt.md](execution-prompt.md).
> **Read order:** this file → [architecture.md](architecture.md) → the phase doc you are executing → [testing.md](testing.md).

## 1. Goal

Remaster Return to Castle Wolfenstein **single player** (via the ioRTCW source port, on Linux):
**modern-FPS movement and gunplay** (CoD4-like numbers as the reference), plus a modern presentation layer (menus, HUD,
optional local AI HD textures and HD audio). Gameplay pillars:

- CoD4-proportioned jog / walk / sprint / crouch speeds
- Snappier crouch transitions and a faster, punchier lean
- Right-click aiming on every firearm: hold-to-ADS (aim down sights) with centered viewmodel,
  FOV zoom, slower movement, tighter spread; scoped rifles show their real scope while held
- Human soldiers walk/run at the same speeds as the player
- A sprint → crouch **tactical slide**
- A CoD4-style **prone** stance (ported from Enemy Territory: Legacy)
- Optional **HD texture** and **HD audio** packs (regenerate locally; never redistribute)

The original game data (`.pk3`) is never modified or copied. All changes live in our
ioRTCW fork and in a separate `fs_game` mod folder named **`codmod`**.

## 2. Hard rules for the execution agent

1. **Phase gating.** Do the phases in order. After each phase: it must compile cleanly,
   the agent writes a short report (what changed, how to test), and then **stops and waits
   for the user to confirm it works in-game**. Do not start the next phase without that
   confirmation.
2. **Do not touch the Steam install.** `~/.local/share/Steam/steamapps/common/Return to Castle Wolfenstein/`
   is read-only for us: we only symlink to it.
3. **Never break the AI.** `bg_pmove.c` runs for the player **and every AI character**, in
   both `qagame` and `cgame`. Every gameplay change must be gated on `!ps->aiChar`
   (see [architecture.md §3](architecture.md#3-the-three-golden-rules)).
4. **Prediction-safe state only.** Any new movement state must live in fields that are
   networked to the client (`pm_flags`, `stats[]`, ...), or client-side prediction will
   jitter. Details in [architecture.md §3](architecture.md#3-the-three-golden-rules).
5. **Everything tunable.** Hard numbers go behind `cod_*` cvars (see
   [architecture.md §5](architecture.md#5-tuning-cvars-cod_)) so the user can tune feel in-game
   without recompiling. Defaults come from [reference-values.md](reference-values.md).
6. **Small, reviewable commits** on the `main` branch of the ioRTCW fork clone (`iortcw/`), one logical
   change per commit, prefixed by phase (e.g. `P2: CoD4 speed scales for player`).
7. No pushing to any remote, no PRs, unless the user asks.
8. The tools named in the original brief ("universal-modder toolset", "rea") **do not exist
   in this environment**. Use the standard shell, git, make, gcc, and podman.

## 3. Phases

| Phase | Doc | Deliverable | Gate |
|---|---|---|---|
| 1 | [phase-1-setup.md](phase-1-setup.md) | Repo layout, ioRTCW clone, build scripts (host plus optional podman), asset symlinks, vanilla build that boots to `escape1`, `codmod` mod folder that loads | User boots the game with both `main` and `fs_game codmod` |
| 2 | [phase-2-movement.md](phase-2-movement.md) | `cod_*` tuning framework, debug HUD, CoD4 speeds, walk, strafe/back scales, crouch smoothing, lean upgrade, soldiers matched to the player's speeds | User confirms the movement feel |
| 3 | [phase-3-ads.md](phase-3-ads.md) | Right-click aiming on every firearm: iron-sight ADS (pmove state, viewmodel centering with per-weapon offsets, FOV, sensitivity, crosshair, move penalty, spread) and hold-to-scope on scoped rifles | User confirms ADS on every supported weapon |
| 4 | [phase-4-gait.md](phase-4-gait.md) | First-person gait presentation: walk/jog/sprint bob, procedural sprint gun-lower, sprint camera weight (RTCW has no FP locomotion anims) | User confirms walk vs jog vs sprint feel |
| 5 | [phase-5-feel.md](phase-5-feel.md) | Movement weight + fire feel: pistol tap-fire, jump/gravity, ground accel/friction, landing slowdown; follow-up quickknife on V | User confirms jump/stop weight, pistol click-fire, and quickknife |
| 5b | [phase-5b-vitals.md](phase-5b-vitals.md) | CoD health regen, CoD-like stamina finish, horizontal health + stamina bars | User confirms regen, stamina, and HUD |
| 5c | [phase-5c-hud.md](phase-5c-hud.md) | CoD on-screen HUD: `clip/reserve` ammo, no health/stamina bars, low-HP blood vignette | User confirms the HUD |
| 5d | [phase-5d-polish.md](phase-5d-polish.md) | Full bind reset, toggle crouch, health-pack clamp, flashlight, always-visible reload anim | User confirms before slide |
| 6 | [phase-6-slide.md](phase-6-slide.md) | Sprint+crouch slide with boost, linear decay, crouch hand-off, camera feel | User confirms the slide |
| 6b | [phase-6b-prone.md](phase-6b-prone.md) | Prone ported from Enemy Territory's GPL code. Tier A: gameplay (stance, bbox, view, speed, transitions, fire/ADS rules). Tier B (optional, cosmetic): ET prone animations retargeted onto BJ's model | User confirms prone (tier A). Tier B only if the user asks |
| 7 (optional) | [phase-7-extras.md](phase-7-extras.md) | Optional polish: ADS sway, recoil, UI extras, etc. | Only if the user asks |
| L0-L2 (optional) | [phase-l10n.md](phase-l10n.md) | Localization: translate menus and game data (L0), AI-transcribe dialogue into subtitles (L1), AI-translate them (L2) | Only if the user asks |

## 4. Project layout (target, created in Phase 1)

```
rtcw-cod/                         ← this folder; its own git repo (docs, scripts, mod files)
├── docs/                         ← these planning docs
├── scripts/
│   ├── setup.sh                  ← clone illescasDaniel/iortcw (codmod), create run/ tree (idempotent)
│   ├── build.sh                  ← build (host by default, --container for podman)
│   ├── install.sh                ← copy built binaries into run/ (main + codmod)
│   ├── run.sh                    ← launch the game (vanilla or codmod, extra args passed through)
├── container/
│   ├── Containerfile             ← optional reproducible build image
│   └── compose.yaml              ← podman-compose service "builder"
├── mod/codmod/                   ← mod files that are NOT compiled (cfg, later pk3 contents)
│   └── codmod.cfg                ← default binds and cvars for the mod
├── iortcw/                       ← clone of illescasDaniel/iortcw (branch "codmod"); git-ignored by the outer repo
└── run/                          ← runtime tree (git-ignored)
    ├── iowolfsp.x86_64           ← copied from the build
    ├── renderer_sp_*_x86_64.so
    ├── main/                     ← symlinks to Steam pk3s + vanilla game .so files
    ├── codmod/                   ← modded cgame/qagame/ui .so files + codmod.cfg
    └── home/                     ← fs_homepath (configs, saves, logs). Keeps ~/.wolf clean
```

## 5. Key facts already verified (2026-10-08)

- ioRTCW upstream base: `438e7d413b5f7277187c35b032eb0ef9093ae778` (2024-05-26). The
  `main` branch on [illescasDaniel/iortcw](https://github.com/illescasDaniel/iortcw) is built
  from that pin; `setup.sh` clones the fork's `main` branch (engine changes already in the fork).
- `make -j32 release` in `iortcw/SP` **builds cleanly on the host** (CachyOS, GCC 16.2.1),
  with no extra packages: it uses bundled headers and libs and links at runtime against the host's
  `sdl2-compat`, `openal`, and `libglvnd`. Output lands in
  `iortcw/SP/build/release-linux-x86_64/`:
  `iowolfsp.x86_64`, `renderer_sp_opengl1_x86_64.so`, `renderer_sp_rend2_x86_64.so`,
  `main/{cgame,qagame,ui}.sp.x86_64.so`.
  → **No container is strictly required.** Phase 1 still adds a small optional podman
  build container for reproducibility. It needs only gcc, make, and git (see phase 1).
- Steam data dir is `.../Return to Castle Wolfenstein/Main` (**capital M**). The engine
  expects `main`. We symlink individual pk3s into `run/main/`.
  SP needs: `pak0.pk3`, `sp_pak1.pk3`, `sp_pak2.pk3`, `sp_pak3.pk3`, `sp_pak4.pk3` (all present).
  Do **not** link `mp_*.pk3` or the Windows `.dll` files.
- **RTCW single player has no prone stance** (prone was added in Enemy Territory). The user owns
  ET (`~/.local/share/Steam/steamapps/common/Wolfenstein Enemy Territory/`). ET's
  GPL source has the prone code (the maintained fork **ET: Legacy**, `github.com/etlegacy/etlegacy`,
  GPLv3, is the primary reference), and its `etmain/pak0.pk3` animations use the **same 53-bone
  skeleton** as RTCW's `bj2` player model. ET: Legacy is an MP-only ET engine: it is a code
  reference, **not** a replacement for ioRTCW (no SP campaign, no RTCW AI). See D2 and [phase-6b-prone.md](phase-6b-prone.md).
- Default RTCW binds (`pak0.pk3` `default.cfg`): `MOUSE1`/`CTRL = +attack`, `MOUSE2`/`SPACE = +moveup` (jump),
  `MOUSE3 / z = weapalt`, `c = +movedown`, `SHIFT = +sprint`, `CAPSLOCK = +speed` (walk), `q/e = lean`,
  `b = +zoom` (binoculars), `g`/`x = +kick`. The mod rebinds `MOUSE2` to ADS (phase 3) and `CTRL` to prone (5b),
  in a binds file applied only on first launch (phase 1.7).
- AI soldiers (`ai_cast_characters.c` ~L56) run at **220 u/s**, walk 90, crouch 80. Vanilla player jog is 256.
- First playable SP map: `escape1`. Cheat-enabled load: `+spdevmap escape1`.

## 6. Decisions & open questions

| # | Topic | Decision / recommendation | Needs user? |
|---|---|---|---|
| D1 | Build environment | Host build is the default, since it is verified working. Podman container is optional, for reproducible builds | No |
| D2 | Prone | Phase 2 speeds up **crouch only**. Prone is its own phase **6b**, after gait (4), feel (5), vitals (5b), CoD HUD (5c) and slide (6): tier A ports ET: Legacy's `PM_CheckProne` gameplay (state in `STAT_COD_FLAGS` + `stats[12]`, `+prone` on `CTRL` via `+wbutton7`). Tier B (optional) retargets ET's prone animations onto `bj2` for third person, personal use only (ET assets are not redistributable). No AI prone | Decided 2026-10-08; renumbered when gait/feel were inserted. Tier B: ask after tier A |
| D3 | ADS input | Hold-to-ADS on `MOUSE2` via the spare `+wbutton6` (`WBUTTON_EXTRA6`), so no engine change is needed. Toggle-ADS also needs no engine change (cfg `vstr` alias, phase 3.1), so both ship and hold is the default bind | Decided 2026-10-08 (default kept) |
| D4 | Scoped weapons (Mauser scope, Snooper, FG42 scope) | Decided 2026-10-08: right-click aims on **every** firearm. Rifles with a scope show their real scope while right-click is held (auto `weapalt` in and out, phase 3.8). Other weapons get iron-sight ADS | Decided |
| D5 | Absolute speeds | RTCW's player scale is very close to CoD4's (eye height 64 vs 60 units), so CoD4 numbers carry over almost 1:1. Jog 200 u/s, sprint 300, see [reference-values.md](reference-values.md) | Decided 2026-10-08: literal CoD4 values, tunable in-game |
| D6 | `g_speed` | **Do not change `g_speed`**: it also drives every AI's speed. Override the player's `ps.speed` in `g_active.c` instead | No |
| D7 | Lean while firing | CoD4 allows firing while leaned and RTCW blocks it. Default: allow (cvar `cod_leanAllowFire 1`) | Decided 2026-10-08 (default kept) |
| D8 | Mod name / cvar prefix | `fs_game codmod`, cvars `cod_*`, new source file prefix `bg_cod*`, `cg_cod*`, `g_cod*` | No |
| D9 | AI speeds | User request: soldiers walk/run like the player. Phase 2.4 sets human AI run/walk/crouch to the player's CoD4 values (`cod_aiSpeedMode 1`), server-only. Monsters and bosses untouched. AI sprinting is a separate, bigger behaviour change (E13) | Decided 2026-10-08. E13 optional |
| D10 | Prone tier B animations | ET has prone animations (verified in `etmain/pak0.pk3`, same skeleton as `bj2`), so tier B uses them. CoD4/WaW animations are only a fallback: they are compiled `xanim` files on a different skeleton (`j_*` bones), so they'd need a full retarget pipeline. Not planned unless ET's fail | Decided 2026-10-08. Tier B itself still optional, after tier A |

## 7. Progress checklist (execution agent: keep this updated)

- [x] Phase 1 — setup & baseline build (confirmed in-game 2026-10-08)
- [x] Phase 2 — movement (confirmed in-game 2026-10-08)
- [x] Phase 3 — ADS core + per-weapon iron-sight bake (all 9, 2026-10-09; tooling kept); `cod_adsCrosshair 2`
- [x] Phase 4 — gait / FP movement presentation (confirmed in-game 2026-10-08); sprint gun raise baked
- [x] Phase 5 — movement weight + fire responsiveness (confirmed in-game 2026-10-08)
- [x] Phase 5.5 — quick knife on V (snappy switch + return-on-swing; confirmed 2026-10-08)
- [x] Phase 5b — health regen, CoD-like stamina, horizontal health/stamina bars (confirmed 2026-10-08)
- [x] Phase 5b follow-up — double ammo + “Press F to interact” / “Breakable” hints (confirmed 2026-10-08)
- [x] Phase 5c — CoD HUD (`clip/reserve` ammo, no bars, low-HP blood; confirmed 2026-10-09)
- [ ] Phase 5d — binds reset, toggle crouch, health clamp, flashlight, reload anim
- [ ] Phase 6 — slide
- [ ] Phase 6b — prone, tier A (gameplay)
- [ ] Phase 6b — prone, tier B (third-person anims, optional)
- [ ] Phase 7 — extras (optional)
- [ ] Phase L0 — translate menus and available game data (optional)
- [ ] Phase L1 — AI-transcribed subtitles (optional)
- [ ] Phase L2 — AI-translated subtitles (optional)
