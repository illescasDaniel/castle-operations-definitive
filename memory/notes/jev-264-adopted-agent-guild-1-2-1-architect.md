---
name: jev-264-adopted-agent-guild-1-2-1-architect
description: On 2026-10-22, rtcw-cod adopted agent-guild 1.2.1 (architect/coder/utility subagents, .claude/development-work
type: decision
date: 2026-10-22
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 264, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-22, rtcw-cod adopted agent-guild 1.2.1 (architect/coder/utility subagents, .claude/development-workflow.md) but deliberately without SDD: removed sdd-feature skill, code-grader agent and the Phase Gate Protocol, because the project is phase-gated by in-game user play-tests (docs/plan.md section 2), not specs/BDD. Delegation rules for this repo live in CLAUDE.md "Project specifics for delegation". Re-running `uvx agent-guild` should use `--without sdd`.

