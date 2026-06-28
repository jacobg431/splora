# Project Notes

## Architecture (from README)

Three-step pipeline:
1. `python splora.py explore <path>` → traverses filesystem, writes JSON to `data/filesystem/`
2. `python splora.py report [--name]` → reads JSON, generates HTML report to `data/report/`
3. `python splora.py boot [--name]` → opens report in browser

## Source Structure

- `splora.py` — CLI entrypoint (empty)
- `src/explore.py` — filesystem traversal logic (empty)
- `src/report.py` — report generation logic (empty)
- `src/boot.py` — browser launcher (empty)
- `data/template/index.html` — HTML report template (empty)
- `data/template/style.css` — styles (empty)
- `data/template/script.json` — unclear purpose (empty; possibly JS config or data injection manifest)

## CLI Options (from README)

explore:
  --name <run-name>   title/filename for the run
  --depth <N>         max subdirectory depth (0 = unlimited)

report:
  --name <run-name>   which JSON file to use (default: last modified)

boot:
  --name <run-name>   which report folder to use (default: last generated)

## Known Data Points to Capture (per README)

- Disk usage (per folder)
- Number of files per folder
- File extension distribution
- File category distribution (Image, Source, Binary, etc.)

## Decided: Tech Stack & Design

- CLI: argparse (stdlib)
- Frontend: Pure JS + ECharts (no framework, no build step)
- Report output: folder with separate assets (not single-file)
- Treemap drill-down (click to zoom, rectangle size = folder size) + left-panel folder tree + info panel below treemap
- Pie charts for extension distribution and category distribution
- V1: single run per report (no comparison)

## Decided: Scale

- Must handle hundreds of thousands of files (e.g. full C:\)
- Optional limits: by file count (--max-files) and/or by time (--timeout)
- Consider --exclude patterns too (node_modules, .git, venv)

## Resolved

- script.json → renamed to script.js ✓
- ECharts: bundled in top-level vendor/ (not under data/) ✓
- Default exclude list: stored in data/config/ (format TBD by agent) ✓
- Bidirectional sync between folder tree and treemap ✓
- Info panel: size + file count + two pie charts (extension + category) ✓
- data/ is for local assets generated or used by the tool; vendor/ is top-level ✓

## Implementation Status

- explore.py ✓ — fully implemented and tested (93 unit + integration tests)
- report.py ✓ — implemented and tested (40 unit + integration tests); copies template + vendor + data.json to data/report/<name>/
- boot.py ✓ — implemented; starts stdlib http.server on first free port ≥5050, opens browser

## Report folder structure

data/report/<safe-name>/
  index.html       ← copied from data/template/
  style.css        ← copied from data/template/
  script.js        ← copied from data/template/
  data.json        ← the raw JSON from data/filesystem/<name>.json
  vendor/
    echarts.min.js ← copied from vendor/

## Open / Flagged Issues

- One minor unresolved: should pyproject.toml include a [project.scripts] entry point (enabling `splora explore ...` after pip install -e .)? Or just python splora.py usage? Flagged to user. (Now resolved: pip-installable entry point is implemented.)

## Proposed File Categories (to be refined by user)

- Image: .jpg .jpeg .png .gif .bmp .svg .webp .ico .tiff .heic .avif .raw
- Video: .mp4 .avi .mkv .mov .wmv .flv .webm .m4v
- Audio: .mp3 .wav .flac .aac .ogg .m4a .wma
- Document: .pdf .doc .docx .xls .xlsx .ppt .pptx .odt .ods .odp
- Source Code: .py .js .ts .java .c .cpp .h .hpp .cs .go .rs .rb .php .swift .kt .sh .bat .ps1 .sql .r .lua
- Data: .json .csv .xml .yaml .yml .toml .db .sqlite .parquet
- Archive: .zip .tar .gz .bz2 .7z .rar .xz
- Executable: .exe .dll .so .dylib .bin .app .msi .deb .rpm
- Font: .ttf .otf .woff .woff2 .eot
- Config: .env .ini .cfg .conf .properties .editorconfig .gitignore
- Other: everything else

## Constraints

- Python 3.13
- agent/temp/ is git-ignored (safe scratch space)
