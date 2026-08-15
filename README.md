# Splora

Splora is a locally hosted, cross-platform file system data visualization tool.

The tool provides a web-based, interactive drill-down feature representing a file system, along with textual and graphical information about files and folders throughout the file system tree. That information includes disk usage, number of files located in each folder, distribution of file extensions, and distribution of file categories (i.e. Image, Source, Binary, etc.).

## Installation

Install Splora in editable mode to make the `splora` command available in your terminal:

```
pip install -e .
pip install -e ".[dev]"   # include development dependencies
```

After installation, both of the following forms work:

```
splora explore <path-to-root-folder>
python splora.py explore <path-to-root-folder>
```

## Getting Started

### The Three Important Commands

Splora must first traverse and document the given file system, before generating the web-based report and showing it to the user. Each of these steps has its own command:

```
splora explore <path-to-root-folder>
splora report
splora boot
```

### Explore

The `explore` command will traverse through the file system located under the given path and continuously write information about the filesystem into a JSON file. All JSON files are located in the [`data/filesystem`](data/filesystem) folder.

This command can be run with the following options:
- `--name <run-name>` The title of the exploration run. Used as the filename for the JSON file and as the title in the HTML report. Defaults to the provided root folder name.
- `--depth <N>` Number of subdirectory levels to traverse. `0` means unlimited (default).
- `--max-files <N>` Stop traversal after visiting N files.
- `--timeout <seconds>` Stop traversal after N seconds have elapsed.
- `--exclude <pattern>` Exclude directories with this exact name. Can be repeated.
- `--no-default-excludes` Disable the built-in default exclude list (see [`data/config/default_excludes.txt`](data/config/default_excludes.txt)).

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

### Report

The `report` command will generate a web-based report by using the files in [`data/template`](data/template) and the information from a JSON file. All reports are located in the [`data/report`](data/report) folder. Reports are self-contained and work offline.

This command can be run with the following options:
- `--name <run-name>` The JSON file name (without the `.json` extension) under [`data/filesystem`](data/filesystem) to use. Defaults to the last modified JSON file.

### Boot

The `boot` command will open the generated report in the browser.

This command can be run with the following options:
- `--name <run-name>` The report folder name under [`data/report`](data/report) to open. Defaults to the last generated report.

## Development

### Running Tests

Install the development dependencies first, then run the full suite:

```
pip install -e ".[dev]"
pytest
```

Tests live under [`test/`](test/), split into two folders:

| Folder | Scope |
|---|---|
| `test/unit/` | Individual functions tested in isolation; uses `tmp_path` for any filesystem interaction |
| `test/integration/` | Full `explore()` command run end-to-end against temporary directory trees |

Useful flags:

```
pytest -v                              # verbose output
pytest test/unit/                      # unit tests only
pytest test/integration/               # integration tests only
pytest -k "test_fmt_bytes"             # run tests matching a name pattern
```

### End-to-end tests

The E2E suite drives the full pipeline — `explore` → `report` → `boot` — as a single session. It is excluded from the default `pytest` run and must be invoked explicitly:

```
pytest test/end2end/
```

The suite invokes `explore` and `report` as real subprocesses, starts the HTTP server in a background thread, runs assertions against all three stages, and deletes the `splora-e2e` run artifacts from `data/` on teardown.

## For Code Agents

This section documents the conventions that any AI agent (regardless of model or provider) must follow when working on this project.

### The `agent/` Folder

[`agent/`](agent/) is the agent's dedicated workspace. It contains two required files and one scratch area:

| Path | Purpose |
|---|---|
| [`agent/log.md`](agent/log.md) | Append-only activity log. One line per entry. |
| [`agent/notes.md`](agent/notes.md) | Living document of design decisions, architecture, and implementation status. |
| [`agent/temp/`](agent/temp/) | Git-ignored scratch space for throwaway files. Safe to write freely. |

**Note about Claude Code:** The [`.claude/`](.claude/) folder exists only for Claude Code's harness machinery compatibility reasons, and all its contents refers back to [`agent/`](agent/).

### Logging Requirements

Every time an agent makes a change to the project — writing or editing files, running commands with side effects, or modifying configuration — it **must** append an entry to [`agent/log.md`](agent/log.md) using this format:

```
[YYYY-MM-DD] <intent> | <action taken> | <outcome>
```

Examples:
```
[2026-06-28] Implement explore.py | Wrote src/explore.py with os.scandir traversal | Smoke tests passed
[2026-06-28] Fix pytest tmp cleanup on Windows | Added tmp_path_retention_policy = "none" to pyproject.toml | Confirmed by user: PermissionError resolved
```

Log entries must be accurate. Do not omit entries for failed attempts — record what was tried and what went wrong.

### Notes Requirements

[`agent/notes.md`](agent/notes.md) is the agent's memory of decisions that are not obvious from the code itself. The agent **must**:

- Read `agent/notes.md` at the start of each session to restore context.
- Update it whenever a design decision is made, a constraint is discovered, or the implementation status of a module changes.
- Keep it current — stale information is worse than no information.

The notes file is not a log. It records *what is true now*, not *what happened*. Superseded decisions should be replaced, not appended.

### Skills

[`agent/skills/`](agent/skills/) holds reusable, repo-specific task instructions. Each skill is a folder named for the task, containing a single `SKILL.md`:

```
agent/skills/
├── commit/SKILL.md
├── pull-request/SKILL.md
└── code-review/SKILL.md
```

Each `SKILL.md` begins with YAML frontmatter (`name` and a one-line `description`) followed by the instructions for carrying out that task in this repository. A skill defines *how a recurring workflow should be done here* — the conventions, defaults, and constraints specific to Splora — so the same task is performed consistently regardless of which agent runs it.

| Skill | Purpose |
|---|---|
| [`commit`](agent/skills/commit/SKILL.md) | Stage and commit the current changes with a short message consistent with the repo history. Does not push. |
| [`pull-request`](agent/skills/pull-request/SKILL.md) | Open a GitHub pull request (via `gh`) based on `main` unless told otherwise. Does not merge or close. |
| [`code-review`](agent/skills/code-review/SKILL.md) | Assess the quality of the current branch's changes (against `main` unless told otherwise), scoped to the modified code only. |

When adding a new skill, follow the same layout: a task-named folder under `agent/skills/` containing a `SKILL.md` with frontmatter and clear, self-sustaining instructions.

### General Guidelines

- **Do not create files outside `agent/`** without explicit user approval. Ask first; implement after.
- **Do not modify `agent/log.md` retroactively.** Entries are append-only.
- **Prefer the existing test conventions** (`pytest`, `tmp_path`, `monkeypatch`) over introducing new testing frameworks.
- **Prefer stdlib** over third-party dependencies. If a new dependency is necessary, discuss it with the user before adding it to `pyproject.toml`.
- **Do not open browsers, send network requests, or modify files outside the repository** without explicit instruction.
- **Keep the test suite green.** Run `pytest` before reporting a task as complete. If tests fail and you cannot fix them, say so explicitly.
- **Always add a log entry** when making a change to the repo before reporting a task as complete.
- **Python version is 3.13.** Do not use syntax or APIs that require a newer version or that were removed in 3.13.
