---
name: pull-request
description: Open a GitHub pull request for the current branch with a fitting title and a clear, human-readable description. Based on main unless told otherwise. Does not merge or close.
---

# pull-request

Create a new GitHub pull request for the current branch using the `gh` CLI.

## Steps

1. Confirm the current branch and that its commits are pushed to the remote (`git status`, `git log origin/<branch>..HEAD`). Push the branch if the PR's commits are not yet on the remote.
2. Determine the base branch. **Default to `main`** unless the user explicitly names a different base.
3. Review the full set of changes the PR will contain (`git diff main...HEAD`) so the title and description reflect everything included, not just the latest commit.
4. Create the PR with `gh pr create --base <base> --title "..." --body "..."`.
5. Report the resulting PR URL back to the user.

## Title and description

- **Title:** a fitting, concise summary of the branch's overall change — not a copy of a single commit message.
- **Description:** self-sustaining and easy for a human reviewer to follow. Aim for:
  - A short **Summary** of what the PR does and why.
  - A **Changes** list (bullets) covering the notable modifications.
  - **Testing / verification** notes when relevant (e.g. `pytest` results, manual checks).
- Write for a human reader who has not seen the conversation. Do not assume prior context.

## Constraints

- **Do not merge, close, or otherwise change the PR's state** after creating it.
- Do not add reviewers, labels, or milestones unless asked.
- Do not modify branch protection or remote settings.
- Creating the PR is the only action — this skill does not update `agent/log.md`.
