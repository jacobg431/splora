# Project Notes

What an agent would otherwise relearn the hard way: design decisions that still bind, lessons
already paid for, and defects known but not yet fixed. For how the code is laid out see
`README.md`; for what is planned see `SPLORA_PLAN.md`.

## Decided: tech stack

- CLI: argparse (stdlib).
- Frontend: pure JS, no framework, no build step; every visualization is a from-scratch SVG widget, with no vendored libraries.
- Report output is a folder of assets, not a single file.
- `boot` serves over HTTP, not `file://`, to sidestep browser security restrictions on local JS.
- One run per report; no multi-run comparison in v1.

## Decided: scale

- Must handle hundreds of thousands of files (e.g. a full `C:\`).
- Optional limits: `--max-files`, `--timeout`, `--depth`, `--exclude`.
- A default exclude list covers `.git`, `node_modules`, `venv`, and the like.

## Decided: frontend design

- Full dark dashboard; elevation reads as a lighter surface (canvas darkest, sidebar above it, cards lightest). A cool-blue accent also carries selection.
- The treemap is the hero, given a landscape height and rendering one level at a time — that single-level render is the drill-down, with an HTML breadcrumb navigating back up. Two donuts (extension share, category share) and the stat cards sit in a supporting row; single column under 1200px.
- Run metadata (name, root, totals, partial badge) lives in the sidebar.
- Every visualization is a `Widget` subclass over a shared base (a lifecycle plus an `on`/`emit` emitter); selection syncs between the folder tree and the treemap through that emitter.
- Treemap layout is squarified (Bruls et al.). A synthetic `(files)` tile fills `size − Σ(child sizes)`, because `size` is cumulative while a node's children are directories only.

## Lessons paid for

**Presentation layering must be acyclic by construction.** The banner and the module holding
the shared terminal primitives once became mutually dependent: the run-frame needed the banner
in order to print it, the banner needed the primitives in order to style itself. In
conventional import position this fails in both directions with a partially-initialized-module
error; moving one import below the definitions it uses fixes it in one direction only — an
order-dependent break that survives until some unrelated import order changes. The root cause
was a single module holding both the widely-used primitives and the composition that consumes
higher-level components, making it both the bottom and the top of the dependency graph. The
correction was the layering rule now enforced by `test/lint/test_imports.py`. An import that
has to move inside a function to break a cycle is evidence the layering is wrong; deferring it
only hides the fault.

**Timing-dependent tests must fake the clock.** `explore`'s deadline is real wall-clock time,
fixed when `Explore` is constructed. Tests that passed a tiny timeout and asserted on a partial
result were racing the runner and failed intermittently on unchanged code. The fix is to
monkeypatch `explore`'s `time.monotonic` with an advancing-sequence stand-in, installed before
`Explore` is constructed, so the deadline is already past at the first check while the real
path stays exercised.

**A test may not buy timing margin with scale.** An earlier end-to-end test interrupted a real
`explore` scan mid-traversal, which meant holding the scan open long enough to deliver a signal
— done with a fixture that wrote 100,000 real files. That cost is not acceptable to impose on
the machine running the tests, so the test and its fixture were removed; `explore`'s response
to a real signal is now covered only at the integration tier (the escalation ladder itself is
still exercised end-to-end against a mock command). A revival must hold a real scan open by
some other mechanism — under `PYTHONUNBUFFERED=1` the child flushes its `Exploring :` line
before the scan begins, which is a usable synchronisation point.

## Known defects, not yet fixed

**The report swap loses the old report on a crash.** `report` removes the destination
directory and then renames the staged tree into it; a crash between the two leaves neither,
silently. The fix is to rename the old report aside, swap the new one in, then delete the one
moved aside. `Report`'s interrupt handling currently carves out an exception for a press
landing mid-swap — the run is left to finish and reports success rather than claiming it was
abandoned — precisely because the same defect would otherwise apply to an interrupt. That
carve-out can be deleted once the rename-aside fix lands.

## Report folder structure

```
data/report/<safe-name>/
  index.html, style.css, main.js, data.js   ← copied from data/template/
  core/, widgets/, ui/                       ← copied from data/template/
  data.json                                 ← the raw scan from data/filesystem/<name>.json
```

While a report is being built it is assembled in `data/report/.<safe-name>.tmp` and swapped
into place when complete. `boot` skips dot-prefixed directories, so one left behind is never
served.

## Constraints

- `tmp_path_retention_policy = "none"` in `pyproject.toml` avoids a Windows `PermissionError` on pytest's symlink cleanup without elevated privileges.
- Two tests are permanently skipped: the symlink cases need elevated privileges on Windows.
