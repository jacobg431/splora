# Project Notes

## Architecture

Three-step pipeline:
1. `splora explore <path>` → traverses filesystem, writes JSON to `data/filesystem/`
2. `splora report [--name]` → reads JSON, generates self-contained HTML report to `data/report/`
3. `splora boot [--name]` → serves report via HTTP and opens browser

## Source Structure

- `splora.py` — CLI entrypoint; argparse subcommands wired to `src/explore.py`, `src/report.py`, `src/boot.py`
- `src/explore.py` — `os.scandir` traversal; `_State` dataclass for limits; CATEGORIES map; atomic JSON write
- `src/report.py` — copies template + vendor assets into `data/report/<name>/`; injects `data.json`
- `src/boot.py` — `http.server` on first free port ≥5050; `_QuietHandler` suppresses request logs; `webbrowser.open()`
- `data/template/` — `index.html`, `style.css`, `script.js` (ECharts treemap UI)
- `data/config/default_excludes.txt` — built-in directory exclude list
- `vendor/echarts.min.js` — bundled ECharts 5; committed to git for offline use

## Decided: Tech Stack & Design

- CLI: argparse (stdlib)
- Frontend: Pure JS + ECharts 5 (no framework, no build step)
- Report output: folder with separate assets (not single-file)
- Treemap drill-down (click to zoom, rectangle size = folder size) + left-panel folder tree + info panel below treemap
- Pie charts for extension distribution and category distribution
- V1: single run per report (no comparison)
- Boot serves via HTTP (not `file://`) to avoid browser security restrictions on local JS

## Decided: Scale

- Must handle hundreds of thousands of files (e.g. full C:\)
- Optional limits: `--max-files`, `--timeout`, `--depth`, `--exclude`
- Default exclude list covers `.git`, `node_modules`, `venv`, etc.

## Frontend Overhaul (branch: `frontend-overhaul`)

Three tracks of active UI/UX work. No implementation has started yet; all tracks are pending decisions and green light.

### Track 1: Treemap Drill-Down

Replace `nodeClick: 'zoomToNode'` (in-place zoom) with a proper drill-down:
- `currentRoot` JS variable tracks the visible level
- On click → `treemap.setOption({ series: [{ data: currentRoot.children.map(toTreemapItem) }] })`
- Manual breadcrumb built from `currentRoot._parent` chain, rendered above the treemap
- Remove ECharts' built-in `breadcrumb` config
- Bidirectional sync with folder tree unchanged

Key constraint: the folder tree already manages a `nodeById` map with `_parent` back-references — reuse this for breadcrumb construction.

### Track 2: CSS Framework

Decision pending. Constraints: no build step; each file must be copyable into `data/report/<name>/vendor/` for offline use.

**Decision: Bootstrap 5 CSS-only. ✓ Implemented.**
- `vendor/bootstrap.min.css` (Bootstrap 5.3.3, 232 KB) committed to repo
- `report.py` copies it into `data/report/<name>/vendor/` alongside ECharts
- `index.html` uses Bootstrap utility classes: `d-flex`, `flex-*`, `overflow-*`, `bg-white`, `border-*`, `p-3`, `text-*`, `fw-*`, `font-monospace`, `text-truncate`, `badge bg-warning`
- `style.css` reduced to design tokens + header/tree/info-panel/chart custom rules only
- 2 new tests added: `test_missing_bootstrap_is_reported` (unit), `test_missing_bootstrap_exits_with_code_1` (integration)

### Track 3: Dashboard Beautification

Framework (Bootstrap 5) now in place. Work includes: color palette, typography scale, treemap label handling, pie chart tooltips/legends, info panel stat cards, hover/focus states, drill-down transition animation. Not yet started.

---

## Implementation Status

All MVP features complete as of 2026-06-28. Frontend overhaul is next (branch: `frontend-overhaul`).

- `explore.py` ✓ — fully implemented and tested (85 unit + 10 integration tests)
- `report.py` ✓ — fully implemented and tested (30 unit + 10 integration tests)
- `boot.py` ✓ — fully implemented and tested (29 unit + 10 integration tests)
- E2E suite ✓ — 24 tests in `test/end2end/`; excluded from default `pytest` run
- CI ✓ — `.github/workflows/continuous-integration.yaml`; ubuntu + windows; ruff format check

## Report Folder Structure

```
data/report/<safe-name>/
  index.html       ← copied from data/template/
  style.css        ← copied from data/template/
  script.js        ← copied from data/template/
  data.json        ← the raw JSON from data/filesystem/<name>.json
  vendor/
    echarts.min.js ← copied from vendor/
```

## File Categories

| Category | Example Extensions |
|---|---|
| Image | .jpg .jpeg .png .gif .bmp .svg .webp .ico .tiff .heic .avif .raw |
| Video | .mp4 .avi .mkv .mov .wmv .flv .webm .m4v |
| Audio | .mp3 .wav .flac .aac .ogg .m4a .wma |
| Document | .pdf .doc .docx .xls .xlsx .ppt .pptx .odt .ods .odp |
| Source Code | .py .js .ts .java .c .cpp .h .hpp .cs .go .rs .rb .php .swift .kt .sh .bat .ps1 .sql .r .lua |
| Data | .json .csv .xml .yaml .yml .toml .db .sqlite .parquet |
| Archive | .zip .tar .gz .bz2 .7z .rar .xz |
| Executable | .exe .dll .so .dylib .bin .app .msi .deb .rpm |
| Font | .ttf .otf .woff .woff2 .eot |
| Config | .ini .cfg .conf .env .properties .editorconfig .gitignore |
| Other | Any extension not listed above |

## Constraints

- Python 3.13
- `agent/temp/` is git-ignored (safe scratch space)
- `tmp_path_retention_policy = "none"` in pyproject.toml — required to avoid Windows PermissionError on pytest symlink cleanup in non-privileged mode
- 2 tests permanently skipped: symlink-related tests require elevated privileges on Windows
