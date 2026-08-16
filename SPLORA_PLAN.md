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
commands; copy-paste "what to do next" advice; an ASCII banner; two new global flags
(`--trim-output`, `--no-color`); and the shared presentation layer that supports them.

**Out of scope:** scan logic, the output JSON schema, the frontend/report template, and the
deferred multi-run comparison view.

### New global flags (defined in `splora.py`, accepted by all three commands)

- `--trim-output` — suppresses the banner and the next-step advice; keeps the functional
  result summary and error output. This is the clean "machine mode." **Tests default to
  `--trim-output`** unless a test is specifically asserting the full decorated output.
- `--no-color` — disables ANSI color. Color usage is derived **solely** from this flag
  (`use_color = not no_color`) — there is no terminal/`NO_COLOR`-env auto-detection for color.

### Module map & ownership

New presentation code is split into three stdlib-only modules; the three command modules
gain small responsibilities. There is intentionally **no** `interrupt.py` — the interrupt
*mechanism* differs too much per command to share, so each command owns its own mechanism,
while the shared *presentation* of an interrupt lives in `terminal.py`.

| Module | Owns |
|---|---|
| `splora.py` | All argparse (subparsers + the shared `--trim-output`/`--no-color` flags); builds the `OutputConfig`; maps each command to its body; invokes the terminal run-frame. Stays thin. |
| `src/terminal.py` | The `OutputConfig` frozen dataclass (`trim`, `no_color`, derived `use_color`) + its factory; ANSI/color helpers; Windows virtual-terminal (VT) enablement; stdout/stderr stream helpers; byte + throughput formatting; the **run-frame** (banner → command body → styled advice); next-step advice styling; and the **styled interrupt-notice** helper. |
| `src/banner.py` | A `Banner` class that renders the emblem + wordmark + version + tagline, with monochrome and trimmed fallbacks. |
| `src/progress.py` | A `Progress` class holding running counters (file count, cumulative size, throughput), a ~10 Hz time throttle, in-place `\r` rendering and a `finish()` method. Renders **only when stderr is a TTY**. |
| `src/explore.py` | Scan logic; `_State` stays a **pure limit-tracker**; drives `Progress` via an explicit reporter passed down the traversal, calling `.record(size)` at the same site files are counted; owns its **inline SIGINT context manager** (first press → set `stopped`, second → force); returns a next-step descriptor. |
| `src/report.py` | Atomic build: stage the report tree in a temp sibling **under `data/report/`**, then swap into place; a `try/finally` removes the temp dir on **any** exit (normal or interrupt); catches Ctrl+C to emit a clean notice; returns a next-step descriptor. |
| `src/boot.py` | Resolve + serve; its existing Ctrl+C handling is kept **inline** (catching `serve_forever`'s `KeyboardInterrupt`) and routed through the shared notice helper. |

### Run flow (one invocation)

1. `splora.py` parses args, then builds `OutputConfig` from them via a `terminal.py` factory.
2. It calls the terminal **run-frame**, passing the chosen command body.
3. The frame prints the **banner** to stdout (skipped under `--trim-output`), then runs the body.
4. The command **body** does its work, prints its own **result summary** to stdout, drives
   progress/interrupt handling, and **returns a next-step descriptor** (command + run name),
   or `None`.
5. The frame prints the **styled next-step advice** derived from that descriptor (skipped
   under `--trim-output`, or when the descriptor is `None` — e.g. on error/`sys.exit` or a
   forced abort).

### Feature specs

**1. Live progress (`explore`)** — a single line updated in place on **stderr** via carriage
return, throttled to ~10 Hz. Shows: files scanned · elapsed · cumulative size · throughput
(files/sec). It is **not** shown when stderr is not a TTY (pipes, CI, redirects), keeping
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
stdout, colored (mono fallback), suppressed by `--trim-output`. The emblem is an ASCII
rendering of the existing SVG logo (a treemap of four blocks at descending opacities), mapped
to the Unicode shade blocks `█ ▓ ▒ ░`. It sits beside a figlet-style `SPLORA` wordmark, with a
tagline and the package version beneath. Exact art, tagline text, colors, and the version
source (`importlib.metadata` with a static fallback) are finalized during implementation.

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
behavior is covered end-to-end.

- **Unit** (pure, no I/O): byte + throughput formatting; the progress throttle decision; the
  `Banner` string; color gating from `--no-color`; the advice string; `OutputConfig`
  derivation; the frame's trim-gating; the interrupt-notice string.
- **Integration** (filesystem I/O, path constants monkeypatched): `report`'s atomic build and
  temp-dir cleanup on both normal exit and simulated failure; `--trim-output` output shape;
  the partial exit code (`3`).
- **End-to-end** (real subprocesses): send a real SIGINT to a live `explore` and assert the
  1st press writes+flags partial output (exit `3`) and the 2nd aborts (exit `130`); `report`
  cancel (exit `130`); `boot` stop (exit `0`); and that `--trim-output` yields clean stdout.
  (Delivering SIGINT on Windows is platform-fiddly and is the known-risky test.)

---

## Deferred Features

- Multi-run comparison view (display two exploration runs side by side)

---

## Optional / Post-MVP Features

- Dark mode toggle in report UI
- Search / filter by name or extension within the report
- Export folder data as CSV
- Configurable file category mappings (user-editable JSON)
- Treemap color coding by category or file age
- Watch mode: automatically re-run explore when the filesystem changes
