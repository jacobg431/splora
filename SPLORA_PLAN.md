# Splora Plan

This document outlines the features that Splora must have, and the progress towards fulfilling these. Its contents are continuously updated as the tool is being developed.

---

## MVP Features ✓

All MVP features are implemented as of 2026-06-28.

### CLI

- `splora explore <path>` and `python splora.py explore <path>` both work (pip-installable entry point)
- `splora report [--name]`
- `splora boot [--name]`

#### explore options
| Option | Description |
|---|---|
| `--name <run-name>` | Title of the run; used as filename and report title. Defaults to root folder name. |
| `--depth <N>` | Max subdirectory depth. `0` = unlimited (default). |
| `--max-files <N>` | Stop traversal after visiting N files. |
| `--timeout <seconds>` | Stop traversal after N seconds elapsed. |
| `--exclude <pattern>` | Exclude directories matching this name. Repeatable. |
| `--no-default-excludes` | Disable the built-in default exclude list. |

#### report options
| Option | Description |
|---|---|
| `--name <run-name>` | Name of the JSON file (without `.json`) under `data/filesystem/` to use. Defaults to last modified. |

#### boot options
| Option | Description |
|---|---|
| `--name <run-name>` | Report folder name under `data/report/` to open. Defaults to last generated. |

---

### Explore

- Traverse the filesystem from the given root path
- Collect per-file metadata: name, size (bytes), extension, category, last modified timestamp
- Collect per-folder aggregates: name, path, total size, file count, extension distribution, category distribution
- Write a hierarchical JSON tree to `data/filesystem/<name>.json`
- Respect the default exclude list at `data/config/default_excludes.txt`
- Respect all CLI flags (`--exclude`, `--no-default-excludes`, `--depth`, `--max-files`, `--timeout`)
- Gracefully stop on limit/timeout and mark the output JSON as partial

### File Categories

Each file is assigned exactly one category based on its extension.

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

---

### Report

- Copy template files (`index.html`, `style.css`, `script.js`) from `data/template/` into `data/report/<name>/`
- Copy `vendor/echarts.min.js` into `data/report/<name>/vendor/`
- Write `data/report/<name>/data.json` from the corresponding `data/filesystem/<name>.json`
- The output folder is fully self-contained: no internet connection required to view it

### Frontend (Report UI)

**Layout:**
```
┌─────────────────────────────────────────────┐
│  [Folder Tree]  │  [Treemap]                │
│                 │                            │
│                 │                            │
│                 ├────────────────────────────│
│                 │  [Info Panel]              │
│                 │  Name / Path / Size / Count│
│                 │  [Ext Pie] │ [Cat Pie]     │
└─────────────────────────────────────────────┘
```

**Treemap:**
- Powered by ECharts (bundled, offline-capable)
- Rectangle area proportional to folder size
- Click a rectangle to drill down into that folder
- Breadcrumb navigation to go back up the tree

**Folder Tree (left panel):**
- Traditional expandable folder tree
- Bidirectional sync with the treemap: selecting a node in either panel updates the other

**Info Panel (below treemap):**
- Displays data for the currently selected folder
- Shows: folder name, full path, total size, file count
- Extension distribution pie chart
- Category distribution pie chart

---

### Boot

- Find the first available TCP port starting at 5050
- Serve `data/report/<name>/` via `http.server.SimpleHTTPRequestHandler` (suppressing per-request logs)
- Open `http://localhost:<port>/` in the system default browser via `webbrowser.open()`
- Serving over HTTP (rather than `file://`) avoids browser security restrictions on local JS modules

---

## Implemented Features

| Component | Status | Notes |
|---|---|---|
| `splora explore` | ✓ | `os.scandir` traversal; atomic JSON write; all CLI flags; partial flag on early stop |
| `splora report` | ✓ | Copies template + vendor assets; writes `data.json`; `--name` or last-modified fallback |
| `splora boot` | ✓ | `http.server` on first free port ≥5050; `webbrowser.open()`; quiet request logging |
| Frontend UI | ✓ | ECharts treemap with drill-down; bidirectional folder tree sync; extension + category pie charts |
| pip entry point | ✓ | `splora` command available after `pip install -e .` |
| Default excludes | ✓ | `data/config/default_excludes.txt`; overridable with `--no-default-excludes` |
| Vendored ECharts | ✓ | `vendor/echarts.min.js` committed; copied into each report for offline use |
| Unit tests | ✓ | 125 tests across `explore`, `report`, `boot` |
| Integration tests | ✓ | 50 tests; monkeypatched path constants; no coupling to real `data/` directories |
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
