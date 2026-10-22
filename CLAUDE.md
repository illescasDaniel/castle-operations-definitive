@AGENTS.md

## Agents and delegation

You are the orchestrator: delegate to the `architect`, `coder` and `utility` subagents in
`.claude/agents/`, and own every approval gate and memory write. Routing, briefs and the memory protocol:

@.claude/development-workflow.md

### Project specifics for delegation

- **No SDD, no `code-grader`.** Phase gating follows `docs/plan.md` §2 rule 1 and `docs/ai-overhaul-plan.md`; record
  the gate status in `memory/activeContext.md`. The user's in-game play-test is the grade.
- **Briefs always carry the safety rules** from `AGENTS.md` (never touch the rend2 present/2D path or `wolfconfig.cfg`;
  `!ps->aiChar` gating in `bg_pmove.c`; tunables behind `cod_*` cvars; user settings vs internal config) and the
  build command (`scripts/build.sh --game-only --install`).
- **Only you launch the game**, never subagents (no forced kills, no benchmarks; see "Running the game" in `AGENTS.md`).
  `utility` may run builds and `git`.
- **Two repos.** Engine and game code live in the `iortcw/` submodule: coders edit and you commit there, push to the
  fork, then commit the bumped pointer in the outer repo. Tell `utility` which repo to commit in. Commit only when asked.
- Menu `.menu` files and HD/audio pk3s are generated and never committed; export `.delta` files instead
  (`scripts/build-menus.sh --export`).
