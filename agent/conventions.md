# Conventions

The rules any agent — regardless of model or provider — must follow when working on Splora.
This file is the source of truth, where a rule is also encoded as a check, the check wins.

## Working agreements

- Escalate design problems instead of coding around them.
- Stay inside the requested scope.
- Ask first before creating files outside [`agent/`](.), opening a browser, sending network
  requests, or touching anything outside the repository.
- Run the tests before reporting a task complete. If they fail and you cannot fix them, say so.
- Encode a convention as a check wherever one can be written.

### How to recognize a design problem worth escalating

Each example below is evidence that the design is wrong, not a technique to reach for. Say
what broke and why before proposing a fix — a workaround that compiles turns a visible fault 
into an invisible one.

- An import that has to move inside a function to break a cycle
- A type error silenced by a cast or an ignore comment
- A test that needs a special case for a single caller
- A parameter threaded through a layer with no use for it
- Code copied because no seam exists to share it
- A mock reaching into private state. 

## The `agent/` folder

[`agent/`](.) is the agent's workspace.

| Path | Purpose |
|---|---|
| [`conventions.md`](conventions.md) | This file. The rules of the repository. |
| [`log.md`](log.md) | Append-only activity log. One line per entry. |
| [`notes.md`](notes.md) | Design decisions, architecture, and implementation status. |
| [`skills/`](skills/) | Instructions for recurring workflows. |
| [`temp/`](temp/) | Git-ignored scratch space. Safe to write freely. |

- **`log.md`** — one line per source-code change, as
  `[YYYY-MM-DD] <intent> | <action taken> | <outcome>`. Facts only, no commentary. Append-only
  and never revised. Failed attempts are logged; documentation-only work is not.
- **`notes.md`** — what is true *now*, not what happened. Read it at the start of a session to
  restore context, and replace superseded content rather than appending to it. Session-scoped
  rationale belongs in `temp/` instead.
- **`skills/`** — one task-named folder per workflow, each holding a `SKILL.md` whose YAML
  frontmatter (`name`, one-line `description`) precedes instructions for carrying out that task
  here. New skills follow the same layout.

[`.claude/`](../.claude/) and [`CLAUDE.md`](../CLAUDE.md) exist only so one particular harness
finds its way here. Both point back at this folder; neither is canonical.

## Python

The language version is **3.13** — no syntax or APIs that need a newer one or were removed in it.

- **Prefer the standard library.** Discuss any new dependency before adding it.
- **Docstrings state purpose, never implementation** — one sentence on one line, ending in a
  period. The code already says how it works, and a second copy only goes stale. Needing more
  than one sentence is a cohesion problem: split the thing instead of lengthening the docstring.
- **Every class and every public function and method carries a docstring.** Nested, dunder, and
  module-level definitions are exempt from needing one, and `test_`-prefixed functions under
  [`test/`](../test/) must not have one at all — the test's name is its description. Anything
  that does carry a docstring obeys the shape rule above.
- **Modules import downward only.** Each module in [`src/`](../src/) occupies a layer and may
  import only from a strictly lower one. In particular, no module is both a dependency sink and
  a composition root.

## Tests

Prefer the existing conventions — `pytest`, `tmp_path`, `monkeypatch` — over new frameworks or
helpers. A test belongs to the narrowest tier that can express it. Any test doing filesystem
I/O that is not end-to-end is an integration test. Unit tests stay pure. The end-to-end tier
can be slow and drives real processes, so it is excluded from the default run and invoked
explicitly.
