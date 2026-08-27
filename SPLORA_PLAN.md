# Splora Plan

This document outlines the features that Splora must have, and the progress towards fulfilling these. Its contents are continuously updated as the tool is being developed.

---

## Implemented Features

| Component | Status | Notes |
|---|---|---|
| `splora explore` | ✓ | `os.scandir` traversal; atomic JSON write; all CLI flags; partial flag on early stop |
| `splora report` | ✓ | Recursively copies the template tree; writes `data.json`; `--name` or last-modified fallback |
| `splora boot` | ✓ | `http.server` on first free port ≥5050; `webbrowser.open()`; quiet request logging |
| Frontend UI | ✓ | From-scratch SVG treemap (squarified, click-to-drill + breadcrumb) and donut charts; bidirectional folder-tree sync; dark dashboard; self-contained ES modules, no vendored libs or build step |
| pip entry point | ✓ | `splora` command available after `pip install -e .` |
| Default excludes | ✓ | `data/config/default_excludes.txt`; overridable with `--no-default-excludes` |
| Unit tests | ✓ | 143 tests across `explore`, `report`, `boot` (2 skipped: symlink cases need elevated Windows privileges) |
| Integration tests | ✓ | 30 tests; monkeypatched path constants; no coupling to real `data/` directories |
| End-to-end tests | ✓ | 24 tests; real subprocesses + daemon HTTP server; artifacts deleted on teardown |
| GitHub CI | ✓ | PR-triggered; ubuntu + windows runners; separate steps per test tier; `ruff format --check` |

---

## Planned: Terminal UX Improvements

Improve the interactive terminal experience of `explore`, `report`, and `boot` — live
feedback, graceful interruption, clearer guidance, and a stronger visual identity — while
preserving Splora's core principles: **zero third-party dependencies (stdlib only)** and
**cross-platform support (Windows + Linux)**. Argument parsing stays entirely in `splora.py`;
this work adds a small presentation layer the commands render through.

### Current behavior (starting point)

- `explore` prints a header, then scans **silently** (no live feedback), then prints a
  summary. Early stops from `--max-files`/`--timeout` are already flagged `partial` in the
  output JSON via a shared `_State` tracker. There is **no `KeyboardInterrupt` handling** —
  Ctrl+C mid-scan raises a traceback and writes nothing.
- `report` deletes then copies the template tree **in place**; a Ctrl+C mid-copy can leave a
  half-written report directory.
- `boot` serves over HTTP and **already** catches Ctrl+C with a clean "Stopped." message.

### Scope

**In scope:** live progress indicator during `explore`; graceful Ctrl+C across all three
commands; copy-paste "what to do next" advice; an ASCII banner; and the shared presentation
layer that supports them. Exactly two global flags are added, `--trim-output` and `--no-color`,
and no others.

**Out of scope:** scan logic, the output JSON schema, the frontend/report template, and the
deferred multi-run comparison view.

**Existing result summaries are preserved.** Every line the three commands already print stays
byte-identical, apart from a few non-ASCII punctuation characters that are replaced by ASCII
equivalents. The new layer only frames those summaries — banner above, live progress during,
advice and notices below.

### New global flags

Both are declared once on a shared argparse parent parser and given to every subcommand, so
each is written after the subcommand it modifies; written before it, they are a usage error.

- `--trim-output` — suppresses the banner and the next-step advice; keeps the functional
  result summary and error output. This is the clean "machine mode." **Tests default to
  `--trim-output`** unless a test is specifically asserting the full decorated output.
- `--no-color` — disables ANSI color. Color usage is derived **solely** from this flag
  (`use_color = not no_color`) — there is no terminal/`NO_COLOR`-env auto-detection for color.

### Module map & ownership

New presentation code is split into small stdlib-only modules arranged in layers; the three
command modules gain small responsibilities. There is intentionally **no** shared interrupt
module — the interrupt *mechanism* differs too much per command to share, so each command owns
its own mechanism, while the shared *presentation* of an interrupt lives with the terminal
primitives.

**Layering rule: a module may import only from a strictly lower layer.** In particular, no
module is both a dependency sink and a composition root. A module holding widely-used
primitives *and* the code that composes higher-level components will cycle as soon as one of
those components needs the primitives — which the banner does. Keeping composition strictly
above the primitives it consumes makes the dependency graph acyclic by construction rather
than by inspection.

| Layer | Module | Owns |
|---|---|---|
| 3 | `splora.py` | All argparse (subparsers plus the shared parent parser carrying the two global flags); builds the `OutputConfig`; selects the command body; hands it to the frame and exits with the code the frame returns. |
| 2 | `src/frame.py` | The **run-frame**: banner → command body → styled next-step advice, returning the body's exit code. Renders the advice, being its only consumer. Receives the body as a callable, so it never imports a command module. |
| 2 | `src/explore.py` | Scan logic; `_State` stays a **pure limit-tracker**; drives `Progress` via an explicit reporter passed down the traversal, calling `.record(size)` at the same site files are counted; owns its **inline SIGINT context manager** (first press → set `stopped`, second → force); returns an outcome. |
| 2 | `src/report.py` | Atomic build: stage the report tree in a temp sibling **under `data/report/`**, then swap into place; a `try/finally` removes the temp dir on **any** exit (normal or interrupt); catches Ctrl+C to emit a clean notice; returns an outcome. |
| 2 | `src/boot.py` | Resolve + serve; its existing Ctrl+C handling is kept **inline** (catching `serve_forever`'s `KeyboardInterrupt`) and routed through the shared notice helper; returns an outcome. |
| 1 | `src/banner.py` | A `Banner` class that renders the emblem + wordmark + version + tagline, with monochrome and trimmed fallbacks. |
| 1 | `src/progress.py` | A `Progress` class holding running counters (file count, cumulative size, throughput), a ~10 Hz time throttle, in-place `\r` rendering and a `finish()` method. Renders **only when stderr is a TTY**. |
| 0 | `src/terminal.py` | The `OutputConfig` frozen dataclass (`trim`, `no_color`, derived `use_color`) + its factory; ANSI/color helpers; virtual-terminal enablement; byte + throughput formatting; and the **styled interrupt-notice** helper, shared because all three commands emit notices. Imports nothing. |
| 0 | `src/outcome.py` | The command-result contract: the exit code a body reports plus an optional next-step descriptor. Kept apart from the presentation primitives so a command body describes its result without depending on how anything is displayed. Imports nothing. |

### Run flow (one invocation)

1. `splora.py` parses args, then builds the `OutputConfig` from them.
2. It calls the **frame**, passing the chosen command body as a callable.
3. The frame prints the **banner** to stdout (skipped under `--trim-output`), then runs the body.
4. The command **body** does its work, prints its own **result summary** to stdout, drives
   progress/interrupt handling, and **returns an outcome**: an exit code plus an optional
   next-step descriptor (command + run name).
5. The frame prints the **styled next-step advice** derived from that descriptor (skipped
   under `--trim-output`, or when there is no descriptor — e.g. after a forced abort).
6. The frame returns the outcome's exit code and `splora.py` exits with it. Bodies report
   ordinary outcomes by returning rather than by exiting, so that advice can still be printed
   ahead of a non-zero code; a body that fails hard exits instead, which passes through the
   frame untouched and correctly suppresses the advice.

### Feature specs

**1. Live progress (`explore`)** — a single line updated in place on **stderr** via carriage
return, throttled to ~10 Hz. Shows files scanned, elapsed time, cumulative size, and
throughput. It is **not** shown when stderr is not a TTY (pipes, CI, redirects), keeping
stdout clean and machine output unpolluted.

**2. Graceful interrupt + unified notices** — a single styled notice helper in `terminal.py`
gives every command a consistent look (glyph/color/channel, honoring `--trim-output` and
`--no-color`), while each command supplies its own honest wording:

- `explore`, **1st** Ctrl+C → stop the scan, write the **partial** JSON (flagged `partial`),
  print the normal partial summary to stdout plus a "stopped early" note.
- `explore`, **2nd** Ctrl+C → force-quit; nothing is written (the atomic `.tmp` file is never
  renamed, so no corrupt output); an **"Aborted."** notice is printed to stdout.
- `report` Ctrl+C → the temp dir is cleaned up; a **"Canceled."** notice is printed.
- `boot` Ctrl+C → a **"Stopped."** notice (this is the intended way to end `boot`).

**3. Next-step advice** — after a command completes, print the exact copy-paste command for
the next step, using the run's actual name: after `explore` → `splora report --name <name>`;
after `report` → `splora boot --name <name>`. Supplied by the command as a descriptor and
styled uniformly by the frame; suppressed by `--trim-output`.

**4. ASCII banner** — an "emblem + wordmark" banner printed once per run at the top, on
stdout, colored with a monochrome fallback, suppressed by `--trim-output`. The emblem is an
ASCII rendering of the existing SVG logo — a treemap of four blocks at descending opacities —
mapped onto a four-step density ramp, so the tiers stay distinguishable when color is off and
shape alone has to carry the depth. It sits beside a figlet-style wordmark, with the tagline
and the package version beneath. The version is read from installed package metadata, falling
back to a static value when the package is not installed.

```
  ##### %%%%%    ____   ____   _      ___   ____      _
  ##### %%%%%   / ___| |  _ \ | |    / _ \ |  _ \    / \
  ##### +++++   \___ \ | |_) || |    | | | || |_) |  / _ \
  ..........     ___) ||  __/ | |___ | |_| ||  _ <  / ___ \
  ..........    |____/ |_|    |_____| \___/ |_| \_\/_/   \_\

  See where your disk went  -  v0.1.0
```

The tagline is adopted in `README.md` as well, so the terminal and the documentation open with
the same line.

**5. All printed output is ASCII** — no byte the tool prints falls outside ASCII, which removes
the need for any encoding-fallback path. When output is redirected to a file, Python encodes it
with the locale encoding rather than UTF-8; on Windows that is a legacy codepage unable to
represent typographic punctuation, so a single such character turns a redirected run into an
encoding error. A few characters already in the codebase carry this fault — an ellipsis and
three dashes, all inside printed strings — and are replaced by ASCII equivalents. Box-drawing
characters used in source comments are never printed and are unaffected.

### Exit-code convention

Distinct exit codes let both humans and scripts/CI distinguish outcomes. Note `2` is
deliberately avoided for "partial" because argparse already uses exit `2` for usage errors.

| Scenario | Exit code |
|---|---|
| Full success · `boot` clean stop (Ctrl+C) | `0` |
| User error (bad path, missing data/assets, etc.) | `1` |
| _argparse usage error (bad flag)_ | `2` (reserved by argparse) |
| `explore` partial — `--max-files`/`--timeout` **or** 1st Ctrl+C | `3` |
| `explore` forced abort (2nd Ctrl+C) · `report` canceled mid-build | `130` (POSIX 128 + SIGINT) |

### Test strategy

Follows the existing tiering, with one rule: **any test that performs filesystem I/O and is
not a full end-to-end test counts as an integration test** (unit tests stay pure). Interrupt
behavior is covered at both the integration and end-to-end tiers.

- **Unit** (pure, no I/O): byte + throughput formatting; the progress throttle decision; the
  `Banner` string; color gating from `--no-color`; the advice string; `OutputConfig`
  derivation; the frame's trim-gating; the interrupt-notice string.
- **Integration** (filesystem I/O, path constants monkeypatched): `report`'s atomic build and
  temp-dir cleanup on both normal exit and simulated failure; `--trim-output` output shape;
  the partial exit code (`3`); and interrupt handling exercised by invoking the installed
  handler directly, which delivers no signal and therefore runs on every platform.
- **End-to-end** (real subprocesses): send a real interrupt to a live `explore` and assert the
  1st press writes+flags partial output (exit `3`) and the 2nd aborts (exit `130`); `report`
  cancel (exit `130`); and that `--trim-output` yields clean stdout while the result summary
  survives it.

  The end-to-end interrupt tests run on **POSIX only**. Delivering an interrupt to a child
  process on Windows needs a different signal and a dedicated process group, and would oblige
  the production code to handle a signal it otherwise never sees — code existing solely to make
  a test reachable. Windows keeps its interrupt coverage at the integration tier instead.

### Lessons from a superseded version of this plan

An earlier version of this plan grouped the presentation code differently, and an
implementation attempt against it failed. The layering rule above exists to prevent a repeat,
so the failure is recorded here rather than left to be rediscovered.

**What failed.** The banner and the module holding the shared terminal primitives became
mutually dependent: the run-frame needed the banner in order to print it, while the banner
needed the primitives in order to style itself. With imports in conventional position this
fails in **both** directions with a partially-initialized-module error. Moving one import below
the definitions it depends on makes the failure disappear in one direction only — an
order-dependent break, which is worse than an outright one, because it survives until some
unrelated import order changes.

**Root cause.** A single module had been given both the widely-used primitives and the
composition that consumes higher-level components. Such a module is simultaneously the bottom
and the top of the dependency graph, and cycles as soon as an intermediate component needs the
primitives. The fault lay in the grouping rather than in any code written against it, which is
why the correction is a layering rule and not a local workaround.

**A second defect from the same cause.** The command-result contract had also been placed among
the presentation primitives, so every command module would have depended on presentation purely
to describe its own return value. Both defects are one failure of cohesion: a single module
accumulating responsibilities from opposite ends of the graph.

**A deferred import does not fix a cycle.** The attempt worked around the cycle with a
function-local import instead of reporting it. Deferring an import is a reasonable tool for
genuinely optional or expensive dependencies; used against a cycle caused by mislayered
responsibilities it merely hides a design fault behind code that appears to work. An import
that has to be moved inside a function is a signal that the layering is wrong.

---

## Deferred Features

- Multi-run comparison view (display two exploration runs side by side)
- Add mypy as CI step. It is already shipped via the project, but not currently enforced.
- Windows delivery for the end-to-end interrupt tests. They currently cover POSIX signal delivery
  only — Windows needs `CTRL_C_EVENT` delivered to a dedicated process group instead of a plain
  `SIGINT`, which is materially more involved to set up correctly.

---

## Optional / Post-MVP Features

- Dark mode toggle in report UI
- Search / filter by name or extension within the report
- Export folder data as CSV
- Configurable file category mappings (user-editable JSON)
- Treemap color coding by category or file age
- Watch mode: automatically re-run explore when the filesystem changes
