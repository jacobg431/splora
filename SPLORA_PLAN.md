# Splora Plan

This document outlines the features that Splora must have, and the progress towards fulfilling these. Its contents are continuously updated as the tool is being developed.

---

## Implemented Features

| Component | Status | Notes |
|---|---|---|
| `splora explore` | ✓ | `os.scandir` traversal; live progress line on a TTY; atomic JSON write; all CLI flags; partial flag and exit 3 on early stop |
| `splora report` | ✓ | Stages the report in a dot-prefixed sibling under `data/report/`, then swaps it into place; injects `data.json`; `--name` or last-modified fallback |
| `splora boot` | ✓ | `http.server` on first free port ≥5050; cooperative poll loop; skips dot-prefixed staging dirs; `webbrowser.open()`; quiet request logging |
| Frontend UI | ✓ | From-scratch SVG treemap (squarified, click-to-drill + breadcrumb) and donut charts; bidirectional folder-tree sync; dark dashboard; self-contained ES modules, no vendored libs or build step |
| Terminal UX | ✓ | Run-frame (banner → command body → next-step advice); `--trim-output` and `--no-color` global flags; all-ASCII output; exit codes `0`/`1`/`3`/`130`/`137`; escalating Ctrl+C — cancel when safe, then abandon, then hard-kill |
| pip entry point | ✓ | `splora` command available after `pip install -e .` |
| Default excludes | ✓ | `data/config/default_excludes.txt`; overridable with `--no-default-excludes` |
| Lint tests | ✓ | 19 tests; AST/token checks for the import-layer map, docstring shape, checker-suppression bans, test-tier boundaries, and interrupt-catch safety |
| Unit tests | ✓ | 252 tests; pure, no filesystem or process I/O |
| Integration tests | ✓ | 148 tests (2 skipped: symlink cases need elevated Windows privileges); filesystem I/O with path constants monkeypatched |
| End-to-end tests | ✓ | 45 tests (4 skipped on Windows: POSIX-only signal delivery); real subprocesses + background HTTP server; artifacts deleted on teardown |
| GitHub CI | ✓ | PR-triggered; ubuntu + windows runners; separate step per test tier; `ruff check` and `ruff format --check` |

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
