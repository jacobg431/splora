---
name: code-review
description: Review the changes on the current branch and assess implementation quality — architecture, design, SOLID, bugs, and test coverage. Scoped to the modified code only. Based on main unless told otherwise.
---

# code-review

Investigate the changes made on the current branch and produce a quality assessment.

## Scope

- Determine the base branch. **Default to `main`** unless the user explicitly names a different base.
- Review the diff against that base: `git diff main...HEAD` (plus uncommitted working changes if the user is reviewing work in progress).
- **Assess only the code that was modified** — the changed blocks and files. Do **not** review or comment on unrelated parts of the repository.
- You *may* judge how the modified code fits the surrounding repository's architecture, design, and conventions — that context is fair game even though the untouched code is not itself under review.

## What to assess

For the changed code, evaluate:

- **Architecture** — does the change fit the existing structure and the three-step `explore → report → boot` pipeline cleanly?
- **Design** — clarity, cohesion, naming, and appropriate separation of concerns.
- **SOLID principles** — single responsibility, sensible abstractions, avoidance of needless coupling.
- **Bugs & correctness** — logic errors, edge cases, error handling, platform concerns (this project runs on Windows and Linux; Python 3.13).
- **Test coverage** — are the changes covered by unit / integration / e2e tests, and do the repo's testing conventions (`pytest`, `tmp_path`, `monkeypatch`) apply?
- **Convention fit** — consistency with the repo's documented agent conventions and existing style.

## Output

Present a written assessment to the user:

- Lead with an overall verdict on implementation quality.
- Group findings by area (architecture / design / bugs / tests / conventions).
- For each finding, reference the specific file and line, state the issue, and suggest a concrete improvement.
- Distinguish blocking problems (bugs, correctness) from optional polish. Call out what is done well, not only what is wrong.

## Constraints

- This is a **read-only assessment**. Do not modify code, stage, commit, or open/merge/close pull requests as part of the review.
- Do not expand the review to the whole repository — stay within the branch's changes.
