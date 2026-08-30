# Conventions

The rules any agent — regardless of model or provider — must follow when working on Splora.
This file is the source of truth, where a rule is also encoded as a check, the check wins.

## Working agreements

- Escalate design problems instead of coding around them.
- Stay inside the requested scope.
- Ask first before creating files outside [`agent/`](.), opening a browser, sending network
  requests, or touching anything outside the repository.
- Run the tests before reporting a task complete. If they fail and you cannot fix them, say so.
- A test may not consume the host's resources at scale to make itself work.
- Encode a convention as a check wherever one can be written.
- Change the smallest span that does the job rather than rewriting a whole class or file, and
  never reach for scripted bulk regex over source.
- Rename code instead of commenting what it does.
- Write docs that stand alone for a reader who wasn't there when they were written, with no
  rejected alternatives, forward references, or code samples in place of a concept.
- Keep `log.md` entries at summary level and check for a missing trailing newline before
  appending, since one can silently swallow the previous entry.

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
| [`notes.md`](notes.md) | Binding design decisions, lessons already paid for, and known-but-unfixed defects. |
| [`skills/`](skills/) | Instructions for recurring workflows. |
| [`temp/`](temp/) | Git-ignored scratch space. Safe to write freely. |

- **`log.md`** — one line per source-code change, as
  `[YYYY-MM-DD] <intent> | <action taken> | <outcome>`. Facts only, no commentary. Append-only
  and never revised. Failed attempts are logged; documentation-only work is not.
- **`notes.md`** — what an agent would otherwise relearn the hard way. Not a substitute for
  `README.md` (how the code is laid out) or `SPLORA_PLAN.md` (what is planned). State what is
  true *now*; replace superseded content rather than appending to it. Session-scoped rationale
  belongs in `temp/` instead.
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
helpers. A test belongs to the narrowest tier that can express it. The lint tier parses source
text and runs no behavior, so it sits outside the filesystem-I/O distinction below. Unit tests
stay pure — no filesystem or process I/O. A test that touches the filesystem is an integration
test, unless it drives a real running process or server, which puts it in the end-to-end tier
instead. The end-to-end tier can take longer to complete compared to other tiers, due to running
real processes, so it is excluded from the default run and invoked explicitly.
