---
name: commit
description: Stage and commit the current working changes with a short, self-sustaining message consistent with this repo's history. Does not push.
---

# commit

Stage the current working changes and record them as a single git commit.

## Steps

1. Inspect the working tree with `git status` and `git diff` (and `git diff --staged` if anything is already staged) to understand exactly what changed and why.
2. Stage the relevant changes. Prefer staging the specific files that belong to this unit of work over a blanket `git add -A` when the working tree contains unrelated changes.
3. Write **one commit** with a short, self-sustaining message (see below).
4. Run the commit. **Do not push** to the remote.

## Commit message style

Match the messages already in this repository. Look at recent history first (`git log --oneline -10`) and stay consistent with it.

- One concise subject line — no separate body is needed for typical changes.
- Capitalized first word; describe *what* changed, and *why* when it isn't obvious.
- When a change has a primary action plus supporting detail, separate the clauses with a semicolon, e.g.
  `Add golden-ratio dimensions for summary cards; adjust #summary-panel styles for better layout and centering`
- Keep it self-sustaining: a reader scanning `git log` should understand the change without opening the diff.
- **No trailers.** Do not append `Co-Authored-By` or any other trailer — the repo history has none.

## Constraints

- Never push, force-push, or touch the remote.
- Do not amend or rewrite existing commits unless explicitly asked.
- Do not create a branch or switch branches as part of committing.
- Committing is the only action — this skill does not update `agent/log.md`. Logging is the responsibility of the implementation work, not the commit step.
