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

## Deferred Features

- Multi-run comparison view (display two exploration runs side by side)

---

## Optional / Post-MVP Features

- Dark mode toggle in report UI
- Search / filter by name or extension within the report
- Export folder data as CSV
- Live progress indicator during exploration (file count, elapsed time)
- Configurable file category mappings (user-editable JSON)
- Treemap color coding by category or file age
- Watch mode: automatically re-run explore when the filesystem changes
