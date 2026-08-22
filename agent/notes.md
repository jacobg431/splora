# Project Notes

## Architecture

Three-step pipeline:
1. `splora explore <path>` → traverses filesystem, writes JSON to `data/filesystem/`
2. `splora report [--name]` → reads JSON, generates self-contained HTML report to `data/report/`
3. `splora boot [--name]` → serves report via HTTP and opens browser

## Source Structure

Production modules sit in layers, and a module may import only from a strictly lower one. The map
is enforced by `test/lint/test_imports.py`, which also rejects any module absent from it.

| Layer | Modules |
|---|---|
| entry point | `splora.py` |
| commands | `src/frame.py`, `src/explore.py`, `src/report.py`, `src/boot.py` |
| components | `src/banner.py`, `src/progress.py` |
| primitives | `src/terminal.py`, `src/outcome.py` |

- `splora.py` — argparse subcommands plus a shared parent parser carrying `--trim-output` and `--no-color`; builds the `OutputConfig` and hands the chosen command body to the frame
- `src/frame.py` — banner, then the command body, then the next-step advice; returns the body's exit code. Takes the body as a callable, so it never imports a command module
- `src/explore.py` — `os.scandir` traversal; `_State` limit tracker; CATEGORIES map; inline SIGINT context manager; atomic JSON write
- `src/report.py` — assembles the report in a dot-prefixed sibling under `data/report/`, then swaps it into place; injects `data.json`
- `src/boot.py` — `http.server` on first free port ≥5050; `_QuietHandler` suppresses request logs; `webbrowser.open()`
- `src/banner.py` — the ASCII emblem, wordmark, tagline and version printed once per run
- `src/progress.py` — the live scan counter, redrawn in place and only when stderr is a terminal
- `src/terminal.py` — `OutputConfig` and its factory, colour helpers, byte and throughput formatting, the shared notice helper
- `src/outcome.py` — the exit-code constants and the `Outcome`/`NextStep` contract a command body returns
- `data/template/` — `index.html`, `style.css`, `main.js` and the ES module tree under `core/`, `widgets/` and `ui/`
- `data/config/default_excludes.txt` — built-in directory exclude list

## Decided: Tech Stack & Design

- CLI: argparse (stdlib)
- Frontend: Pure JS, no framework, no build step. **Migrating off ECharts** to from-scratch SVG widgets — see "Frontend Overhaul" below. ECharts is still in the code until the treemap is replaced.
- Report output: folder with separate assets (not single-file)
- Folder tree in the sidebar (moved out of the content area); treemap is the report's hero element
- V1: single run per report (no comparison)
- Boot serves via HTTP (not `file://`) to avoid browser security restrictions on local JS

## Decided: Scale

- Must handle hundreds of thousands of files (e.g. full C:\)
- Optional limits: `--max-files`, `--timeout`, `--depth`, `--exclude`
- Default exclude list covers `.git`, `node_modules`, `venv`, etc.

## Frontend Overhaul (branch: `frontend-overhaul`)

### Status of the original three tracks

- **Track 2 (CSS framework)** — Bootstrap 5.3.3 CSS-only was vendored and wired in. *Now under review:* with the full-custom dark redesign below, Bootstrap's role shrinks to a few flex/spacing utilities. Open decision: keep it or drop it (see "Open decisions").
- **Track 1 (treemap drill-down)** — never implemented in ECharts. It is **absorbed into the from-scratch treemap**: rendering only the children of the current level *is* the drill-down.
- **Track 3 (beautification)** — supersedes into the design direction below.

### Consolidated design direction (decided 2026-08-14, via user Q&A)

The light content area read as a different, blander app bolted onto the liked dark sidebar. The redesign makes everything share the sidebar's world and builds all visualizations from scratch.

**Visual language**
- **Full dark dashboard.** One cohesive dark surface; the sidebar stops feeling bolted-on.
- **Elevation = lighter.** Canvas is the darkest layer, sidebar sits above it, cards are lightest:
  - canvas `#15161f` · sidebar `#1e2030` (existing) · card `#262a3d` (hover/raised a touch lighter)
- **Accent: cool blue** (`#6ea8fe` primary, `#93c5fd` light) — already implied by the logo and current selection color. Drives active tree row, selected treemap tile, key numbers, links, focus rings. Selection tint = `rgba(110,168,254,0.15)`.
- **Soft cards.** Rounded corners + subtle dark-tuned shadow, **no hard borders** (kill the current 1px black borders). Optional hairline `rgba(255,255,255,0.06)` for definition only.
- **Typography scale** needs a real ramp (current `.stat-label` 16px vs value 28px is wrong). Establish `--fs-*` tokens; labels small/uppercase/muted, values large.

**Layout**
- **Treemap is the hero**, arranged *treemap on top, supporting row below*:
  - ≥1200px: full-width treemap hero (row 1); charts (2 donuts) + stat cards in a supporting row (row 2).
  - <1200px: single column — treemap → charts → stats.
  - Note: a full-width hero treemap should **not** stay locked to 1:1 (would be enormous). Give it a generous landscape height (e.g. ~55–60vh or a wide aspect). This revises the earlier 1:1 decision.
- **Run metadata lives in the sidebar** (name / root path / total files / total size / partial badge), placed below the logo header and above the tree; hidden when the sidebar is collapsed. This finally rehouses the header metadata dropped when the sidebar landed.

**Visualizations: build from scratch, remove ECharts entirely**

Rationale (user): highest payoff for consistency and authenticity is to own the rendering. Graphical widgets become fully-qualified domain models.

- **Render tech: SVG.** Each tile/segment is a real DOM element → CSS styling, `:hover`/`:focus`, accessibility, and easy drill-down transitions come for free. Node counts stay modest because the treemap only renders one level at a time.
- **Architecture: shared `Widget` base + subclasses.** Base defines the lifecycle (`mount`/`setData`/`render`/`resize`/`destroy`) and a small event emitter (`on`/`emit`); `Treemap` and `Donut` extend it. Shared theme tokens + layout math live in helper modules.
- **JS structure: native ES modules** via `<script type="module">` (works because `boot` serves over HTTP, not `file://`). Proposed layout under `data/template/`:
  ```
  index.html
  style.css
  main.js                 (entry, type="module")
  core/widget.js          (base Widget + event emitter)
  core/theme.js           (JS-side color/series palette, tokens)
  core/svg.js             (tiny SVG element helpers)
  core/layout.js          (squarified treemap layout; donut arc math)
  widgets/treemap.js      (Treemap extends Widget — includes drill-down + breadcrumb)
  widgets/donut.js        (Donut extends Widget)
  ui/tree.js, ui/sidebar.js
  data.js                 (fetch + registerAll + nodeById map)
  ```
- **Treemap layout algorithm:** squarified (Bruls et al.) for good aspect ratios. Reuse the existing `nodeById` + `_parent` back-references for breadcrumb construction.
- **Charts:** custom SVG donuts with a curated, dark-tuned series palette (no ECharts rainbow). Top-N: extensions ~10, categories ~11 (as today).

**Rollout sequence (charts first, treemap last — de-risks incrementally):**
0. **Shell/theme foundation** ✓ (commit ee36d28): dark palette + tokens, soft cards, typography, treemap-hero layout, sidebar metadata, `Widget` base + theme/svg helpers. ECharts still inside for the treemap + donuts.
1. **Replace the donuts** ✓: from-scratch `widgets/donut.js` (`Donut extends Widget`) with SVG ring, on-arc labels for large slices, hover emphasis (grow + dim others), and a center readout (total by default; slice %/name/value on hover). Arc geometry in `core/layout.js` (`polarToXY`, `annularSectorPath` with full-ring special case, `donutArcs`). Donuts self-resize via the `Widget` ResizeObserver, so they are no longer in `resizeAll`. ECharts now drives only the treemap.
2. **Replace the treemap** ✓: `core/layout.js` gained `squarify` (Bruls et al.); `widgets/treemap.js` (`Treemap extends Widget`) renders one level at a time as SVG tiles with an HTML breadcrumb. Clicking a folder tile drills in (sets `_current`); clicking a leaf selects it; breadcrumb crumbs navigate up. A synthetic `(files)` tile fills `size − Σ(children sizes)` since `size` is cumulative and children are dirs only. Selection syncs via the `Widget` event emitter: treemap `emit('select', path)` → `selectNode(path,'treemap')`; external selection → `treemap.showNode(node)` (drills if the node has children, else shows its parent with the tile highlighted). Removed the ECharts treemap, `toTreemapItem`, `DARK_TOOLTIP`, and all resize plumbing (every widget self-resizes via ResizeObserver). ECharts is now loaded but unused.
3. **Drop ECharts** ✓: removed the `<script>` tag and `vendor/echarts.min.js`. With Bootstrap already gone, `vendor/` is now empty and retired — `report.py` lost `_VENDOR_DIR` and the vendor param/copy/check entirely (`_missing_assets(template_dir)`, `_build_report(out_dir, template_dir, raw_json)`); reports are pure template + `data.json`, ~1 MB lighter. The frontend is now fully self-contained: no vendored libraries, no build step.

**The overhaul is complete.** Every visualization is a from-scratch SVG `Widget`; the report ships only its own ES modules + `data.json`.

**Docs debt:** `SPLORA_PLAN.md` still describes the old ECharts/Bootstrap/vendor approach (Frontend Overhaul tracks, "Powered by ECharts", vendored-asset rows). It needs a pass to match reality — this notes file is the current source of truth.

**`report.py` / test impact (do not forget):**
- The asset set changes from a single `script.js` to `main.js` + module directories. `report.py` (`_missing_assets`, `_build_report`) and its unit/integration/E2E tests must be updated to copy/verify the new files.
- `echarts.min.js` copy logic + any ECharts-related checks are removed in step 3.
- No JS test framework is introduced (matches repo convention: Python/pytest only). Pure layout math stays untested by the suite, as `script.js` is today.

### Resolved decisions

- **Bootstrap: DROP it** (user, 2026-08-14). Remove `vendor/bootstrap.min.css`, replace its utility classes with our own small CSS, delete the `report.py` copy logic and the 2 bootstrap tests. Folded into step 0.
- **First chunk: step 0 only, then review** (user, 2026-08-14). Build the dark shell + `Widget`/helper scaffolding with ECharts still inside; stop for review before touching any viz.

---

## Implementation Status

MVP complete, frontend overhaul complete, terminal UX in progress on branch
`terminal-ux-improvements`.

- 18 lint + 217 unit + 128 integration tests run by default (2 skipped: symlink cases need
  elevated Windows privileges); 45 end-to-end tests invoked explicitly
- CI ✓ — `.github/workflows/continuous-integration.yaml`; ubuntu + windows; ruff format check

### Terminal UX

Done: the layered presentation modules above, the two global flags, the live progress line, exit
codes `0`/`1`/`3`/`130`, graceful interrupt in all three commands, the atomic report build, and
all-ASCII output.

Deferred, and deliberately not started:

- **End-to-end interrupt tests.** Holding a scan open long enough to signal it needed a fixture
  writing 100,000 real files, which is not an acceptable cost to impose on the machine running
  the tests. Any revival must hold the scan open without scaling file creation. Interrupt
  behaviour is meanwhile covered at the integration tier on every platform, by driving the
  handler the scan installs. A working synchronisation point was found and is worth reusing:
  under `PYTHONUNBUFFERED=1` the child flushes its `Exploring :` line before the scan begins.
- **The second Ctrl+C is nearly unreachable.** The first press makes the scan unwind in
  microseconds, and the handler is restored before the JSON is serialised and written — measured
  at 1.22s for a 1.68M-file scan. A second press almost always lands in that window and produces
  the bare traceback the feature exists to remove. The fix is to extend the interruptible region
  over the write, capturing the summary wording and exit code before it so a late press cannot
  contradict what was already serialised.
- **The report swap loses the old report on a crash.** The swap removes the destination and then
  renames the staged tree into it. A crash between the two leaves neither, and silently. The fix
  is to rename the old aside instead, swap in, then delete the one moved aside.

## Report Folder Structure

```
data/report/<safe-name>/
  index.html   ← copied from data/template/
  style.css    ← copied from data/template/
  main.js      ← copied from data/template/
  data.js      ← copied from data/template/
  core/        ← copied from data/template/
  widgets/     ← copied from data/template/
  ui/          ← copied from data/template/
  data.json    ← the raw JSON from data/filesystem/<name>.json
```

While a report is being built it is assembled in `data/report/.<safe-name>.tmp` and swapped into
place when complete. `boot` skips dot-prefixed directories so one left behind is never served.

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
