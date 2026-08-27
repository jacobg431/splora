---
name: familiarize
description: Familiarize yourself with the Splora repository and make sure to understand its purpose, architecture, general layout, and conventions. Do not make any edits to the repository or any of your existing memory files. Expect further instructions after completing the skill.
---

# familiarize

Build working context on the Splora repository before starting a task that requires
repository familiarity.

## Steps

1. Read `README.md` — the repository's source of truth for purpose, architecture, usage, and
   test tiers.
2. Read [`agent/conventions.md`](../../conventions.md) — the rules of the repository.
3. Read `SPLORA_PLAN.md` — implementation status and deferred/planned features.
4. Read [`agent/notes.md`](../../notes.md) — working notes and lessons learned carried across
   sessions. 
5. Skim the `src/` files and `test/` directory structure.
6. Read through the `test/lint/` directory to understand the linting rules and conventions 
   mechanically applied to the codebase.
7. Check current repository state: `git status`, current branch, and `git log --oneline -10`.
8. Read the tail of [`agent/log.md`](../../log.md) (last ~10-15 entries) for recent activity not
   yet folded into the docs above.

## Output

Present a brief summary to the user covering:

- The project's purpose and three-step pipeline.
- The layered architecture and where the current branch's likely area of work sits.
- Current implementation status and any deferred/open items relevant to ongoing work.
- Any conventions worth flagging before starting the next task.

Keep it brief — this is a working recap, not a full report.

## Constraints

- **Read-only.** Do not edit, stage, or commit any repository file, and do not write to any
  memory file.
- Do not run the test suite or any other command beyond the read-only git inspection above.
- After presenting the summary, stop and wait for further instructions.