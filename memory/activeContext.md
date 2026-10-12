_Last updated: 2026-10-12_

## Branch

`cursor/use-iortcw-fork-0f47` (outer) — points setup at the published iortcw fork.

## Current focus

Wire castle-operations-definitive to [illescasDaniel/iortcw](https://github.com/illescasDaniel/iortcw) (`codmod` branch) so `setup.sh` no longer `git am`s `patches/`. Companion engine PR: https://github.com/illescasDaniel/iortcw/pull/2 (clean branch; #1 closed — red staging Actions only).

## Blockers

None for the fork/setup switch. Full game playtest still needed on the user's machine (no Steam data in this cloud env).

## Just changed

- iortcw fork: branch `cursor/codmod-patches-0f47` (+ mirror `codmod`) with all 64 patch commits' content (83 files); PR #1 → `master`.
- Outer: `setup.sh` defaults to clone fork `codmod`; README/docs/credits/plan/phase-1/execution-prompt updated; `patches/` kept as export backup only.

## Next steps

1. User: review/merge https://github.com/illescasDaniel/iortcw/pull/1
2. User: locally `rm -rf iortcw && ./scripts/setup.sh && ./scripts/build.sh && ./scripts/install.sh` and smoke-test HUD/menus/movement
3. Optional: add `illescasDaniel/iortcw` to the cloud agent environment repos so future agents can `git push` the fork directly
