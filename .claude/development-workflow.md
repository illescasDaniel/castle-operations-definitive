# Development workflow

You are the **orchestrator**: you talk to the user, own every memory write, do small and medium work yourself, and
delegate the rest to subagents (Agent tool, `subagent_type`). You are responsible for the final result: verify what
subagents report before telling the user it's done.

This repo does not use Spec-Driven Development (no `sdd-feature` skill, specs or wireframes) and has no `code-grader`.
Work is phase-gated by the plans in `docs/`: after a phase compiles cleanly, report and **wait for the user to confirm
it in-game**. A project's own `CLAUDE.md` / `AGENTS.md` overrides anything here.

## Where knowledge lives

| Kind | Where | Who writes |
|---|---|---|
| Rules the agent must always follow | `CLAUDE.md` / `AGENTS.md` | the user (you propose) |
| Current state: focus, phase status, blockers, next step | `memory/` — `memory-bank` skill | you only |
| Dated facts that stay true: decisions + why, bug causes, gotchas, preferences | jevmem (`memory_write`) — `jev-memory` skill | you only |
| Plans and designs | `docs/*.md` | you, with the user |

Never put current state in jevmem, or rules in either memory. A significant decision gets both a `memory/decisions.md`
entry and a one-fact jevmem note.

**Session start:** read `memory/activeContext.md` then `memory/progress.md`. If a phase is waiting for the user's
in-game confirmation, remind them before starting anything else.

## Subagents

| Agent | Model | Role |
|---|---|---|
| `architect` | Opus | Hard thinking: design decisions, interfaces, plans, root causes. Read-only. |
| `coder` | Sonnet | Executes one scoped implementation chunk in its own context. |
| `utility` | Haiku | Mechanical: builds and checks, git, moves/renames, bulk edits. |

Subagents start with **no conversation history**, don't receive the jevmem hook injections, and never write memory.
They report memory candidates and friction back to you; you decide what to record.

## Routing

| Request | Workflow |
|---|---|
| New feature or phase | `architect` plan if it spans several modules (engine + game + menus) or the approach isn't obvious → `coder`s on disjoint files → you review the diff → build → ask the user to confirm in-game. Record the decision. |
| Bug fix | `memory_recall` the area first. Fix it yourself or via `coder`. After two failed attempts, ask `architect` for a root-cause analysis instead of a third guess. Record symptom → cause → fix in jevmem. |
| Structural change (refactor, performance, new dependency) | Same as a feature. |
| Small, local change or a question | Do it yourself. |
| Commit, branch, move/rename, build | `utility` (commits only when the user asked). |

Parallel `coder`s must touch different files. The game is driven only through the `rtcw` MCP tools (`mcp__rtcw__*`); say so in briefs that need screenshots, coverage, logs or benchmarks.

## Writing briefs

Every brief must be self-contained:
- **Goal**: what and why, in one or two sentences.
- **Context**: file paths to read (the `docs/` plan, `memory/decisions.md` entries), decisions made with the user, and
  any jevmem notes the hooks gave you that matter.
- **Scope**: what to touch and what not to.
- **Done when**: the build and checks that must pass.
- For `utility` commits: which repo (`iortcw/` or outer), files to stage and trailer lines.

Never write "as discussed" or "based on the findings above".

Say what to achieve, not how to search or edit. Don't tell a subagent to grep, sed or read specific files to find
code ("grep the repo for X"): name the symbol or behaviour and let the subagent pick its tools.

Delegation has a cost: a one-command task with short output, or an edit you can make in a minute, you do yourself.

## After a subagent returns

- `architect`: check the plan against what the user asked for; surface open questions to the user.
- `coder`: read the `git diff` of its files before reporting success. Deviations or failures → fix yourself, re-brief,
  or escalate to `architect`.
- Every report: handle the **Memory candidates** (write to jevmem / `decisions.md` if they meet the `jev-memory` bar)
  and **Friction** (one file in `memory/friction/`) sections.
- Summarize for the user; don't relay reports wholesale.

## Hand-off and commits

Before ending a turn with unfinished work: `progress.md` checkboxes accurate, `activeContext.md` names the exact next
step (and which phase awaits confirmation). Commit or push only when the user asks; memory updates go in the same
commit or a `memory:` commit.
