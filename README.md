# Castle Operations Definitive

**Castle Operations Definitive** (`codmod`) is a single-player remaster of **Return to Castle Wolfenstein**, built on
the [ioRTCW](https://github.com/iortcw/iortcw) source port (engine fork:
[illescasDaniel/iortcw](https://github.com/illescasDaniel/iortcw)). It plays like a modern shooter and looks and sounds
better, while the campaign stays RTCW.

> **Status: early development (pre-release).** This is the first public snapshot, not a final release. Things will
> change, and some parts are rough. Developed and tested on **Linux** only; Windows is untested. Issues and feedback
> are welcome.

It started as a movement and gunplay overhaul and grew well beyond that: HUD, menus, a new renderer feature set,
frame pacing, 3D audio, controller support and optional AI-remastered textures and audio. `codmod` is the internal
name (the **Cod** in **C**astle **O**perations **D**efinitive): the mod folder, `fs_game codmod`, and the `cod_*` cvars.

You need your own copy of RTCW (Steam). **No game data is included or modified.** See [Legal](#legal).

## Features

### Movement and gunplay
- Modern-FPS-proportioned walk / jog / sprint speeds; AI soldiers move at the same speeds as the player
- Faster, smoother crouch transitions, a punchier lean/peek (fire while leaned), and movement weight (acceleration,
  friction, jump, landing slowdown)
- **Aim down sights on every firearm**: hold or toggle, per-weapon iron-sight alignment, FOV zoom, lower sensitivity,
  slower movement and tighter spread. Scoped rifles show their real scope while aiming
- **CoD-style recoil**: every shot kicks your real aim, with a per-weapon kick that climbs while you hold fire, can be
  pulled back down, and recovers when you stop; less while aiming, crouched or prone (`cod_recoil*`)
- **ADS weapon sway and breathing**: slow breathing drift of the weapon while aiming, reduced when crouched or prone and
  increased when moving (`cod_adsSway*`)
- **AI soldiers sprint**: human enemies break into a short burst of speed (x1.5) when charging a distant target or
  running to cover; `cod_aiSprint 0` restores vanilla (`cod_aiSprint*`)
- Sprint with a procedural gun-lower, walk/jog/sprint bob, hipfire cone that tightens when standing still
- Modern-FPS fire modes (click-fire for pistols, bolt and semi-auto), tap-fire pistol, always-visible reload animation
- **Quick knife** (`V`), **tactical slide** (sprint + crouch), **prone** (`CTRL`, ported from Enemy Territory: Legacy), toggle crouch
- Health regeneration, linear stamina, hit markers with headshot ticks
- **Fully dynamic flashlight** (`L`): a per-pixel spot light that lights walls, enemies and props alike and
  **casts real-time shadows** (see [docs/flashlight-shadows.md](docs/flashlight-shadows.md))
- Everything is tunable: ~190 `cod_*` cvars and an in-game `cod_menu` tuning overlay; `cod_enable 0` restores vanilla feel

### HUD and menus
- Modern-FPS HUD: `clip/reserve` ammo with heat colouring, 4-post bloom crosshair, ADS dot, low-health blood vignette,
  "Press F" interact hints
- Rebuilt options menus: one clear GRAPHICS page plus an ADVANCED tab with labelled defaults and a restore button,
  separate SOUND, GAME and CONTROLS pages (CONTROLLER and MOUSE & KEYBOARD), settings that actually persist
- Built-in performance benchmark (real-time demo replay, microsecond frame stats, 1% lows), per-pass GPU profiler
  (`r_gpuProfile`) and deterministic screenshot diffs; renderer sync stalls and wasted passes removed with no visual
  change, for +65% FPS over stock rend2 in our benchmark (183 -> 303 FPS)

### Controller support
- Xbox and PlayStation pads through SDL GameController, one modern-FPS layout for both
- Pad-aware menus (directional focus), pad glyphs in interact hints, auto-detected controller family
- Look sensitivity, stick smoothing, axial snap, and an optional ADS-only auto-aim assist
- **Gyro aiming** (DualSense): off, while aiming, or always, with its own sensitivity (see [docs/gyro.md](docs/gyro.md))

### Graphics
- Uses the **rend2** renderer with sun shadows, sun rays, per-pixel **dynamic lights** (which also light characters,
  props and items), specular and deluxe mapping, HDR, 16x anisotropic filtering
- **Ambient occlusion** with a menu option (Off / SSAO / **GTAO**, GTAO by default), depth-aware upsampling and distance
  fade, see [docs/ssao.md](docs/ssao.md)
- **SMAA** anti-aliasing (4 quality levels) as the default, ~18% faster than 2x MSAA in our benchmark; MSAA 2/4/8x
  still available. One `Anti-Aliasing` menu row drives both
- **Frame pacing**: an engine-level limiter with absolute deadlines (sleep + spin) for a flat frame-time graph, sub-millisecond
  game-time interpolation so camera motion is even at any cap, and five **VSync** modes (Off / On / Adaptive / Triple /
  Low latency) plus a frame limit slider and a separate menu/cutscene frame cap (Auto = monitor refresh), all in the menu
- Wayland-friendly fullscreen and mode switching
- Cutscenes: black letterbox bars, any key skips, and a **Skip Intro** toggle in Settings > Game
- **Remastered cutscene videos** (optional, local): the intro and menu loops, see [HD videos](#hd-videos-optional-local-only)
- **Remastered textures** (optional, you generate them locally): AI-upscaled with Real-ESRGAN, see below

### Audio
- **3D audio**: OpenAL Soft **HRTF** binaural rendering for headphones, on by default, toggle in the sound menu
- **Remastered audio** (optional, you generate it locally): AI-improved (AudioSR) 48 kHz sound effects, dialogue and music

## Requirements

- Linux (developed on CachyOS; other distros should work)
- RTCW installed via Steam (SP `.pk3` files)
- Build tools: `gcc`, `make`, `git`, `python3`
- Runtime libs the engine links against: SDL2, OpenAL, OpenGL (typical desktop install)

Optional: Podman + podman-compose for a containerized build (`scripts/build.sh --container`).

## Setup (first time)

From the repo root:

```bash
./scripts/setup.sh
./scripts/build.sh
./scripts/install.sh --vanilla
```

What that does:

1. **`setup.sh`** — checks out the `iortcw/` submodule ([our ioRTCW fork](https://github.com/illescasDaniel/iortcw), branch `main`) if missing, creates `run/`, symlinks Steam SP paks into `run/main/`, links mod configs into `run/codmod/`.
2. **`build.sh`** — builds ioRTCW SP on the host.
3. **`install.sh --vanilla`** — copies the engine into `run/` and game modules into both `run/codmod/` and `run/main/` (vanilla kept for A/B). Later rebuilds usually use `./scripts/install.sh` (codmod only).

Menus: RTCW's own menu files are game data and are not redistributed. The repo stores only our changes (`mod/codmod/menu-deltas/`); `setup.sh` / `install.sh` rebuild the full menus and `codmod_menus.pk3` from your RTCW install automatically (needs `python3`). Details: [`docs/menus.md`](docs/menus.md).

If your Steam data is not in the default path, point `RTCW_DATA` at the game’s `Main` folder:

```bash
RTCW_DATA="/path/to/Return to Castle Wolfenstein/Main" ./scripts/setup.sh
```

Default: `~/.local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main`.

## Run

`scripts/run.sh` launches from `run/` and loads **codmod by default**. Extra args are passed straight to the engine.

```bash
# Codmod (default)
./scripts/run.sh

# Codmod + first SP mission (cheats / spdevmap)
./scripts/run.sh +spdevmap escape1

# Reset binds and settings to the mod defaults (mod/codmod/codmod_defaults.cfg)
./scripts/run.sh --reset-binds +spdevmap escape1

# Windowed
./scripts/run.sh --windowed 1280x720 +spdevmap escape1

# Vanilla (no codmod), for comparison
./scripts/run.sh --vanilla +spdevmap escape1
```

| Flag | Effect |
|------|--------|
| *(default)* | `fs_game codmod`; the engine then runs `codmod_defaults.cfg` and `codmod.cfg` |
| `--vanilla` | Play with `main` only (no mod) |
| `--reset-binds` / `--reset-settings` | Full reset via `codmod_defaults.cfg` (binds + AA, frame limit, pacing, vsync defaults; same as `/cod_resetbinds`) |
| `--windowed WxH` | Windowed mode, e.g. `1280x720` |

Configs, saves, and `rtcwconsole.log` go under `run/home/` (not `~/.wolf`).

### Day-to-day rebuild

After gameplay code changes:

```bash
./scripts/build.sh --game-only
./scripts/install.sh
./scripts/run.sh +spdevmap escape1
```

Full rebuild (engine too): `./scripts/build.sh` then `./scripts/install.sh`.

## Useful in-game console

Prefix console commands with `/` when typing in the tilde console (e.g. `/god`). Inside `.cfg` files, plain `set` is fine.

| Command | Notes |
|---------|--------|
| `spdevmap escape1` | Load first level with cheats |
| `god` / `give all` / `noclip` | Standard cheats |
| `cod_menu` | In-game tune overlay for `cod_*` cvars (arrows adjust; F5 dumps) |
| `cod_debugHud 1` | Movement / ADS / stamina debug readout |
| `cod_enable 0` | Temporarily disable mod behaviour for A/B |
| `cod_resetbinds` | Full reset to codmod defaults: keybinds (ADS, quickknife, toggle crouch, flashlight, pad, …) plus AA (`r_aa`), frame limit, pacing and vsync. Same as `exec codmod_binds.cfg` or `./scripts/run.sh --reset-binds` |

Default codmod binds (after reset): `MOUSE2` ADS, `V` quickknife (pad: R3 tap = quickknife, hold = kick), `C` toggle crouch, `L` flashlight, `CTRL` prone.

### Controllers (Xbox + PlayStation)

SDL GameController is enabled by default (`in_joystick 1`, analog sticks on). One modern-FPS `PAD0_*` map covers both brands (Cross/Circle/Square/Triangle = A/B/X/Y positions). Pad binds are re-applied every launch from `codmod.cfg`; `/cod_resetbinds` refreshes keyboard + pad.

| Input | Action |
|-------|--------|
| Left / right stick | Move / look |
| LT·L2 / RT·R2 | ADS / fire |
| LB·L1 / RB·R1 | Grenades / next in bank |
| A·Cross / B·Circle / X·Square / Y·Triangle | Jump / crouch (hold→prone) / reload (hold→interact) / next weapon |
| LS·L3 / RS·R3 | Sprint / quick knife (tap R3), kick (hold R3) |
| D-pad | Reload / prone / flashlight / prev weapon |
| Back·Share / Start·Options | Notebook / pause |

Interact hints show **F** on keyboard, or an original X / Square glyph (Xbox-like / PlayStation-like art in `codmod_pad.pk3`) when last input was a pad. Toggle with `cod_padGlyphs`. Family is auto-detected (`in_gamepadFamily`).

Pause menu: **SAVE / LOAD / SETTINGS / EXIT**; SETTINGS holds CONTROLS, GRAPHICS, SOUND, GAME. CONTROLS splits into **CONTROLLER** and **MOUSE & KEYBOARD**. Controller: Look X/Y (`cod_padSensX` 0.5 / `cod_padSensY` 0.35) and Auto-Aim (ADS-only snap to closest visible enemy, off by default). Always-on pad feel: axial look snap, stick smoothing, move cardinal snap, LOS friction. Tap **X / Square** reload; hold interact. Tap Circle/B crouch; hold ~0.4s prone.

More testing notes: [`docs/testing.md`](docs/testing.md).

## HD textures (optional, local only)

SP textures can be AI-upscaled into a local `run/codmod/codmod_hd.pk3`. The **tool is in git**; the **pk3 is not** (proprietary source art — regenerate on each machine).

Full steps: [`tools/hd-textures/README.md`](tools/hd-textures/README.md).

Quick regenerate (current pack: **general-wdn @ 2×**, JPEG 90; needs NVIDIA CUDA + [uv](https://github.com/astral-sh/uv)):

```bash
cd tools/hd-textures
uv sync
uv run hd-textures batch --model general-wdn --scale 2 --jpeg-quality 90 --out samples/full
uv run hd-textures pack --from samples/full --pk3 ../../run/codmod/codmod_hd.pk3
```

`codmod.cfg` already sets `r_picmip 0` / `r_picmip2 0`. Restart or `/vid_restart` after rebuilding the pk3.

The texture fixes (`codmod_zfix.pk3`) and specular maps (`codmod_spec.pk3`) are derived from your paks and built automatically by `scripts/setup.sh` / `scripts/install.sh` (needs numpy + Pillow); after regenerating `codmod_hd.pk3` the next install rebuilds them. Force with `scripts/build-derived-packs.sh --force`.

## HD audio (optional, local only)

SP audio can be AI-remastered to 48 kHz into a local `run/codmod/codmod_hd_audio.pk3`.
The **tool is in git**; the **pk3 is not**. Locked recipe: **`sr_only`** (SFX/VO) +
music **`sr_linked`**.

Full steps: [`tools/hd-audio/README.md`](tools/hd-audio/README.md).

```bash
cd tools/hd-audio
./remaster.sh          # batch (~1360 files, hours) + pack; resumes if interrupted
# or: ./remaster.sh --pack-only
```

Works on **8 GB** GPUs. Close other GPU apps before a full batch.

## HD videos (optional, local only)

The intro cutscene and the menu background loops can be AI-remastered into a local `run/codmod/codmod_hd_video.pk3`
(MJPEG/AVI; the engine prefers `video/<name>.avi` over the original RoQ and falls back when the pk3 is absent).
The **tool is in git**; the **pk3 is not**. Locked recipe: ffmpeg `nlmeans` denoise (strength 1) →
[2xLiveActionV1_SPAN](https://openmodeldb.info/models/2x-LiveActionV1-SPAN) by **jcj83429** (2x) → dynamic film grain.

Full steps: [`tools/hd-video/README.md`](tools/hd-video/README.md).

```bash
cd tools/hd-video
uv sync --python 3.11
uv run hd-video batch --variant nlm1+span --grain 3
uv run hd-video pack --variant nlm1+span
```

## Localization (community patches)

The game data is English-only: no translated text or audio ships with RTCW on Steam, and the menus and HUD of this mod
are English too. The Steam community has packs with the original text and audio extracted from the French, Spanish,
Italian and German retail CDs. Ones we know of:

- German: <https://steamcommunity.com/sharedfiles/filedetails/?id=340192909>
- Spanish: <https://drive.google.com/file/d/1wBzt80dru3EISKH87oIKQkxOwBwps-M5/view>
- French and Italian: look in the RTCW guides on Steam Community.

These are third-party downloads, not made by or affiliated with this project, and we have not tested them with codmod.
Use them at your own risk. Mission text and voices may come out translated while the menus and HUD added by this mod
stay English. Nothing from them is included in this repo. Real translation support is only planned:
[`docs/phase-l10n.md`](docs/phase-l10n.md).

## What is in the engine and what is in the mod

Most of the work is code in the [iortcw fork](https://github.com/illescasDaniel/iortcw), not in the `codmod` folder:

- **Engine fork (`iortcw/`, C code):** all the mechanics (movement, ADS, recoil, slide, prone, health regen, AI sprint),
  the HUD and `cod_menu` tuning overlay, the renderer work (GTAO, SMAA, bloom, colour grade, dynamic lights and
  flashlight shadows, specular, GPU profiling), controller and gyro input, video playback, frame pacing, and the
  multi-language and subtitle code. About 31k lines changed against upstream ioRTCW (about half of that is the
  generated SMAA lookup table).
- **Mod folder (`mod/codmod/`, no compiled code):** default config and key binds, menu patches (`menu-deltas`),
  translated strings, and a few small assets (hitmarker sounds, pad glyphs, cursor).
- **Tools (`tools/`):** optional local pipelines that build the private HD texture, audio and video packs, plus
  localization, subtitle and specular-map tools. The generated packs are never in this repo.

The engine defaults to vanilla RTCW behaviour (`cod_enable 0`, renderer features off). The mod's config files in
`mod/codmod/` switch the features on, so `codmod` is the mod and the engine only provides the capabilities. Details:
[`docs/architecture.md`](docs/architecture.md) section 0.

## Development

Contributor docs start at [`docs/plan.md`](docs/plan.md). Engine changes live in the
[iortcw fork](https://github.com/illescasDaniel/iortcw) (`main` branch); menus are edited as
described in [`docs/menus.md`](docs/menus.md).

### AI-assistant files (optional, can be disabled)

The repo includes the author's AI-assistant setup: `AGENTS.md` / `CLAUDE.md`, the `memory/` notes, `.claude/` and
`.cursor/` skills, and a project MCP server (`jevmem`, a long-term memory tool launched with `uvx`). If you open the
repo in Claude Code or Cursor, these may run automatically (the `SessionStart` / `UserPromptSubmit` hooks in
`.claude/settings.json` call `uvx jevmem`). You do not need any of it to build or mod the game. To turn it off:

- **Claude Code:** create `.claude/settings.local.json` (personal; already in `.gitignore`) with `{ "disableAllHooks": true }`,
  or delete the `hooks` block from `.claude/settings.json`. Decline the project MCP server when prompted, or remove
  the `jevmem` entry from `.mcp.json`.
- **Cursor:** remove the `jevmem` entry from `.cursor/mcp.json`.
- Or delete `.claude/`, `.cursor/`, `.mcp.json` and `skills-lock.json` locally. Nothing in the build uses them.

## Layout (short)

```
rtcw-cod/
├── docs/                 # plan, phase docs, design notes, credits
├── scripts/              # setup, build, install, run
├── tools/hd-textures/    # local AI upscale pipeline (uv); outputs git-ignored
├── tools/hd-audio/       # local AI audio remaster (uv); outputs git-ignored
├── tools/hd-video/       # local AI video remaster (uv); outputs git-ignored
├── mod/codmod/           # configs, menu deltas, small original pk3s (not compiled)
├── iortcw/               # git submodule: illescasDaniel/iortcw (own repo)
└── run/                  # runtime tree (git-ignored)
```

## Project status

First public snapshot of an ongoing project. The gameplay phases, controller support, menus, SMAA, frame pacing and
3D audio are implemented and play-tested on Linux; the HD packs are optional and generated locally. Known gaps:
Windows and macOS are untested, VSync modes 1-3 are not validated on every driver, and install paths and script
flags may still change. Design notes and history: [`docs/plan.md`](docs/plan.md), [`docs/`](docs/), [`memory/progress.md`](memory/progress.md).

## Legal

- **Castle Operations Definitive is an unofficial fan project.** It is not affiliated with or endorsed by id Software,
  Gray Matter, Activision, Bethesda or Microsoft. *Return to Castle Wolfenstein* and any other game names mentioned
  are trademarks of their respective owners.
- You must own RTCW. The scripts only **symlink** your Steam `.pk3` files; they are never copied, modified or redistributed.
- AI-upscaled textures and AI-improved audio are derived from the original game assets, so the **generated packs are not
  distributed**. The tools in `tools/` produce them on your machine. Check the licenses of the models they download
  (Real-ESRGAN, AudioSR).
- Engine and game-code changes (the [iortcw fork](https://github.com/illescasDaniel/iortcw) `main` branch)
  and the scripts in this repository are released under the **GNU GPL v3 with ioRTCW's
  additional terms**, see [`LICENSE`](LICENSE). The engine is derived from the id Software RTCW source release and ioRTCW.
- Third-party code and ideas (SMAA, Enemy Territory: Legacy prone, OpenAL Soft, ...) are credited in [`docs/credits.md`](docs/credits.md).
