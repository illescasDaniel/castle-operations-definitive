_Last updated: 2026-10-12_

## Public release prep (2026-10-12)
Project renamed in docs to "Castle Operations Definitive" (`codmod`). README rewritten (features, pre-release status, Legal), `LICENSE` (ioRTCW GPLv3 + terms), `setup.sh` now applies `patches/` (62, re-exported) and finds Steam data without a hardcoded path, home paths removed from tools. History squashed to one initial commit 2026-10-12 (pre-squash backup bundle: `../rtcw-cod-pre-squash.bundle`). Outer repo remote: castle-operations-definitive.

Done since: ET: Legacy attribution in `PM_CodCheckProne`; menus moved to deltas + `scripts/menus.py` (see decisions.md).

Legal review done 2026-10-12: menu deltas v2 (references, no original passages), model credits/licenses, Ani4K now downloads from Sirosky/Upscale-Hub, home paths removed, CoD wording softened, README Development section explains disabling the AI-assistant hooks/MCP. Engine fork published (see Fork section); `menus.txt`/`ingame.txt` are near-verbatim RTCW lists; keep `../rtcw-cod-pre-squash.bundle` private (old menus).

## Branch

`cursor/use-iortcw-fork-0f47` (outer, PR) / `codmod` (iortcw, tracks `origin` = illescasDaniel/iortcw).

## Current focus

No HUD / invisible pause menu in-game was caused by a rend2 perf edit (`RB_SwapBuffers` presenting `msaaResolveFbo`, which drops all 2D drawn after post-process when MSAA is on). Engine side of the benchmark attempt shelved; clean engine rebuilt + installed. Awaiting user playtest.

## Blockers

None.

## Just changed

- iortcw: everything except `SP/code/ui/ui_shared.c` stashed as "failed benchmark attempt (engine: bench + rend2 perf + HUD hacks)" (the separate diff file was deleted; stash is the only copy).
- Rebuilt (`scripts/build.sh`) + installed (`scripts/install.sh`). User confirmed HUD + pause back.
- `run/home/codmod/wolfconfig.cfg` restored from pre-wipe `reset-bak-20261011-160725` (the agent's `--reset-config` had left stock RTCW binds: MOUSE2 jump, CTRL attack, no PAD binds). Benchmark cvars stripped; previous file kept as `wolfconfig.before-restore-*.cfg`.
- Outer repo: benchmark menus already in outer `git stash` "failed benchmark attempt". Working tree still has guardrail leftovers based on the wrong diagnosis (`codmod.cfg` forced `set cg_draw2D…` block, `run.sh --reset-config` + guardrail `+set`s); harmless, candidates for cleanup.

- Safeguards: `run.sh` rolling `wolfconfig` backups (`run/home/codmod/cfg-backups/`, newest 15); removed `--reset-config` + forced-cvar guardrails (reverted `codmod.cfg`/`run.sh`); rules in `docs/testing.md` + `AGENTS.md`. Automated HUD smoke test tried and dropped (menu click + cutscene before HUD).

## Benchmark (rebuilt 2026-10-11)

Built + installed: `cl_benchDemo` engine stats, `scripts/bench.sh`, menu RUN BENCHMARK (options.menu DISPLAY), demo in `mod/codmod/demos/`. CLI verified (2 runs, wolfconfig unchanged). HUD + ESC pause confirmed by user (loaded save). Awaiting user: menu button. Observed large run-to-run variance (96.7 vs 78.9 avg fps) — use 3+ runs.

## Next steps

1. User: launch normally, confirm HUD + ESC pause menu in a map.
2. Decide on outer leftovers (keep/revert guardrails; keep `controls_kb.menu` parse fix + MangoHud logging).
3. If a benchmark is retried: rend2 perf ideas must keep the 2D pass reaching the backbuffer (resolve after 2D, not after post-process).

## Performance investigation (2026-10-11)

Benchmark tooling extended (`--set/--env/--gpumon`, engine `MAX_CONSOLE_LINES` 32→64). Result: GPU-bound; no free wins, see `docs/performance.md` Findings. Next: HD audio remaster (`tools/hd-audio/remaster.sh`).

## HD audio remaster (2026-10-12)
Full remaster finished; `run/codmod/codmod_hd_audio.pk3` packed (private, not committed). hd-audio tool now falls back to plain resample when AudioSR fails (lowpass cutoff / very short files). Next: user playtests audio; delete the pk3 to revert.

## SMAA (2026-10-12)
Plan written: `docs/smaa.md` (SMAA 1x in `RB_PostProcess` after tonemap, before 2D; `r_smaa` 0-4, default High; MSAA default 0; present path untouched). Implemented and committed, built+installed, benchmarked: SMAA 3 = 225 FPS vs MSAA 2x 190 (+18%). User playtest passed (SMAA works, HUD/menus fine). Credits in docs/credits.md. r_aa now persists (engine default 3, archived; codmod.cfg no longer forces it); codmod_binds.cfg resets r_aa + frame limit/pacing/vsync (menu RESET SETTINGS, run.sh --reset-binds/--reset-settings). Menu now has ONE row `r_aa` (0 off, 1-4 SMAA, 5-7 MSAA 2/4/8) -> R_ApplyAA drives r_smaa + MSAA latch; menus pk3 repacked by hand (python zipfile; no `zip` binary).

## FPS limiter (2026-10-12)
Implemented all of `docs/fps-limiter.md` (pacer, present hooks, `r_vsync` 0-4, cgame sub-ms, menu rows). Built + installed, bench-verified; NOT committed (iortcw + outer). User to review: HUD + ESC pause (swap hook touched in `sdl_glimp.c`), menu rows in GRAPHICS > DISPLAY, feel at a cap (e.g. 144, mode 2).

## HRTF 3D audio (2026-10-12)
Done and playtested by user ("sounds AMAZING"). `s_alHRTF` On/Off (default On; auto mode dropped, it never triggered), `s_alHRTFProfile`, menu row in sound menus, `s_volume` locked to 1.0 in codmod.cfg. Details: `docs/audio-3d.md`. Committed in both repos.

## Fork switch (2026-10-12)
`iortcw/` origin is now https://github.com/illescasDaniel/iortcw (old origin renamed `upstream`); `setup.sh` clones the fork's `codmod`, no `git am`. Fork branches `codmod` and `cursor/codmod-engine-0f47` (PR #2) were force-pushed with the real 65-commit history (local tag `codmod-pre-fork-backup`). `patches/` has since been removed (see decisions.md). HD pk3s stay in `run/codmod/` (checksums verified unchanged after setup/build/install). Next: user playtest (HUD, ESC, HD assets), review/merge fork PR #2, then this PR; `../iortcw` (sibling clone) is redundant.

## Verification (2026-10-12)
setup.sh verified in place and from a fresh clone (clones fork `main`, no patches); fresh-clone and in-place builds + install OK; AGENTS.md/README/docs updated for fork-only engine flow; `patches/` removed. Fork now has only `main`.

## Menu FPS limit (2026-10-13)
Implemented `com_maxfpsMenu` + `com_maxfps -1` Auto; built + installed, uncommitted. Awaiting playtest.
