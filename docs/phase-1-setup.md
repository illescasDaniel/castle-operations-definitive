# Phase 1 — Linux Workspace Setup & Baseline Build

**Goal:** a reproducible workspace. It builds unmodified ioRTCW SP (engine plus
`cgame`/`qagame`/`ui`) and boots the Steam game data through the engine, both as vanilla
(`main`) and through an empty `codmod` mod folder.

**No gameplay code changes in this phase.**

## Facts already verified (do not re-research)

- Host build works with no extra packages: `cd iortcw/SP && make -j$(nproc) release` with
  GCC 16.2.1 on CachyOS. It links at runtime against the host's `libSDL2-2.0.so.0` (sdl2-compat),
  `libopenal.so.1`, and `libGL.so.1`, which are all installed.
- Podman 6.1.3 and podman-compose are installed. Docker is not, and is not needed.
- Steam data: `~/.local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main/`
  holds `pak0.pk3 sp_pak1.pk3 sp_pak2.pk3 sp_pak3.pk3 sp_pak4.pk3` (needed) plus `mp_*`
  and Windows `.dll` files (ignore).
- The user's shell is **fish**. Scripts must be `#!/usr/bin/env bash` files and must not rely on
  being sourced.

## Tasks

### 1.1 Outer repo
- Already done: the outer repo exists (branch `main`), with the docs and a `.gitignore`
  (`iortcw/`, `run/`, `*.log`, `build*/`) committed. Commit the scripts, container, and mod files of this phase on top.

### 1.2 ioRTCW clone (pinned)
```bash
git clone https://github.com/iortcw/iortcw.git iortcw
git -C iortcw checkout -b codmod 438e7d413b5f7277187c35b032eb0ef9093ae778
```
All engine and game changes in later phases are commits on `iortcw`'s `codmod` branch.
`scripts/export-patches.sh` runs `git -C iortcw format-patch 438e7d4..codmod -o patches/`,
so the outer repo keeps a backup.

### 1.3 `scripts/setup.sh` (idempotent)
1. Clone ioRTCW if `iortcw/` is missing (as in 1.2).
2. Create `run/main`, `run/codmod`, `run/home`.
3. Symlink **each** required pk3:
   `run/main/<pak>.pk3 → $RTCW_DATA/<pak>.pk3` for `pak0 sp_pak1 sp_pak2 sp_pak3 sp_pak4`.
   `RTCW_DATA` defaults to the Steam `Main` path above and can be overridden by an env var.
   Fail with a clear message if any pak is missing.
4. Symlink `run/codmod/codmod.cfg → ../../mod/codmod/codmod.cfg` and
   `run/codmod/codmod_binds.cfg → ../../mod/codmod/codmod_binds.cfg`.

Why individual symlinks instead of linking `Main/` itself: the folder must be named
lowercase `main`, we must place our own `.so` files inside it without writing into the
Steam folder, and we must keep the `mp_*.pk3` multiplayer paks out of the SP search path.

### 1.4 `scripts/build.sh`
```
scripts/build.sh [--container] [--debug] [--clean] [--game-only]
```
- Host (default): `make -C iortcw/SP -j"$(nproc)" release` (or `debug`).
  - `--game-only` adds `BUILD_CLIENT=0` for fast iteration on gameplay code (only the 3 `.so` files).
  - `--clean`: `make -C iortcw/SP clean`.
- `--container`: `podman-compose -f container/compose.yaml run --rm builder <same make args>`
  with `BUILD_DIR=build-container`, so container and host objects never mix.
- Print the output directory at the end and exit non-zero on failure.

### 1.5 Optional podman build container
Only gcc, make, and git are needed (ioRTCW bundles SDL2/zlib/jpeg/ogg/vorbis/opus/freetype
headers and libs). Use an older glibc base, so binaries built in the container also run on
newer hosts.

`container/Containerfile`
```dockerfile
FROM docker.io/library/debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential git ca-certificates pkg-config \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src/iortcw/SP
```

`container/compose.yaml`
```yaml
services:
  builder:
    build: { context: ., dockerfile: Containerfile }
    image: localhost/rtcw-cod-builder:latest
    userns_mode: keep-id          # files created in the bind mount stay owned by the user
    volumes:
      - ..:/src:Z
    working_dir: /src/iortcw/SP
    entrypoint: ["make"]
    command: ["-j8", "release", "BUILD_DIR=build-container"]
```
Acceptance for the container (optional): `scripts/build.sh --container` produces the same
file set in `iortcw/SP/build-container/release-linux-x86_64/`, and that `iowolfsp.x86_64`
runs on the host.

### 1.6 `scripts/install.sh`
```
scripts/install.sh [--vanilla] [--build-dir DIR]
```
- Source: `iortcw/SP/build/release-linux-x86_64/` (or `--build-dir`).
- Always copy (not symlink) the engine into `run/`: `iowolfsp.x86_64`,
  `renderer_sp_opengl1_x86_64.so`, `renderer_sp_rend2_x86_64.so`. The engine loads
  renderers from its own directory.
- Copy `main/{cgame,qagame,ui}.sp.x86_64.so` → `run/codmod/`.
- `--vanilla`: also copy them → `run/main/`. **Run this only once, in Phase 1**, so `run/main`
  keeps pristine vanilla game modules for A/B comparison. Later phases install only to
  `run/codmod/`.

### 1.7 `scripts/run.sh`
```
scripts/run.sh [--vanilla] [--reset-binds|--reset-settings] [--windowed WxH] [extra engine args...]
```
Runs from `run/`:
```bash
./iowolfsp.x86_64 \
  +set fs_basepath "$RUN" +set fs_homepath "$RUN/home" \
  +set vm_game 0 +set vm_cgame 0 +set vm_ui 0 \
  +set sv_pure 0 +set logfile 2 \
  [+set fs_game codmod +exec codmod.cfg]   # omitted with --vanilla
  [+exec codmod_binds.cfg]                 # codmod only: first launch (no run/home/codmod/wolfconfig.cfg) or --reset-binds
  [+set r_fullscreen 0 +set r_mode -1 +set r_customwidth W +set r_customheight H]
  "$@"
```
- `fs_homepath` inside `run/home` keeps configs, saves, and `rtcwconsole.log` out of `~/.wolf`.
- Pass-through example: `scripts/run.sh +spdevmap escape1`.
- Two config files, on purpose:
  - `codmod.cfg` runs **every** launch: aliases (`+ads`, `+prone`) and `cod_*` overrides. Never `bind` here,
    or it would overwrite the user's own rebinds every time the game starts.
  - `codmod_binds.cfg` is a **full** bind reset (`unbindall` → `default.cfg` → codmod deltas)
    on first launch, `--reset-binds` (alias `--reset-settings`), menu Defaults / RESET SETTINGS (codmod), or
    `/cod_resetbinds` (phase 5d). The same file also resets the user-facing display defaults: `r_aa` (SMAA High),
    `com_maxfps`, `com_maxfpsMode`, `r_vsync`.

### 1.8 `mod/codmod/codmod.cfg` (initial)
Comment header plus a marker so we can confirm it was executed:
```
// codmod default config — executed by scripts/run.sh
echo "^2codmod.cfg loaded"
```
`mod/codmod/codmod_binds.cfg` (initial): only `echo "^2codmod_binds.cfg applied"`. Binds arrive
in phases 3 and 4b.
(ADS binds are added in phase 3.)

### 1.9 Smoke test (agent-side)
1. `scripts/setup.sh && scripts/build.sh && scripts/install.sh --vanilla`
2. `ldd run/iowolfsp.x86_64` has no "not found".
3. Launch (this opens a window on the user's Wayland desktop):
   `timeout 60 scripts/run.sh --windowed 1280x720 +spdevmap escape1`
   then check `run/home/codmod/rtcwconsole.log` for:
   - `Loading DLL file: .../run/codmod/qagame.sp.x86_64.so` (and cgame/ui). The exact wording
     may differ, so grep for `qagame.sp`.
   - `codmod.cfg loaded`
   - No `ERROR:` / `Couldn't load` / `sp_pak... checksum` warnings.
4. Same with `--vanilla` (log lands in `run/home/main/rtcwconsole.log`).

If DLLs fail to load from `run/codmod/` (some ioq3 builds restrict DLL search paths), check
`FS_FindVM` in `qcommon/files.c` and report back. Don't work around it silently.

## Acceptance criteria (gate)

- [ ] `scripts/build.sh` builds cleanly from a fresh clone; `--game-only` works.
- [ ] Optional: `scripts/build.sh --container` works.
- [ ] `scripts/run.sh` → main menu → New Game / `spdevmap escape1` plays, with sound,
      mouse look, and saves working (vanilla and codmod).
- [ ] Log shows the game modules loaded from `run/codmod/` when running the mod.
- [ ] Short report to the user, then **stop** and wait for confirmation.

## Instructions to give the user at the end of Phase 1

```bash
cd rtcw-cod
scripts/run.sh                     # the mod (identical to vanilla in phase 1)
scripts/run.sh --vanilla           # pure ioRTCW for comparison
scripts/run.sh +spdevmap escape1   # jump straight into the first level with cheats on
```
Useful console commands (`~` key): `cg_drawFPS 1`, `god`, `noclip`, `give all`,
`r_mode -1; r_customwidth 2560; r_customheight 1440; vid_restart`.

## Troubleshooting notes

| Symptom | Try |
|---|---|
| Black window or crash at start on Wayland | `SDL_VIDEODRIVER=x11 scripts/run.sh` (XWayland) |
| No sound | `+set s_useOpenAL 1` or `0` to switch backend |
| "Couldn't load default.cfg" | pk3 symlinks broken. Re-run `scripts/setup.sh` and check `ls -lL run/main` |
| Wrong pak checksum warnings | Steam files may be modified. Verify integrity in Steam |
| Mouse feels off | `+set in_mouse 1`, `cl_mouseAccel 0` (default.cfg already sets 0) |
