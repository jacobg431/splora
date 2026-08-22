# Splora

*see where your disk went*

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

### Options Every Command Accepts

Both flags are written *after* the subcommand they modify.

| Option | Effect |
|---|---|
| `--trim-output` | Print only the result summary, leaving out the banner and the next-step advice. |
| `--no-color` | Disable coloured output. Colour is switched off automatically when output is not a terminal, so a redirected or piped run is already plain. |

### Exit Codes

Each command reports what happened through its exit code, so a script can tell a complete run from a truncated one.

| Meaning | Code |
|---|---|
| Success, including stopping `boot` with Ctrl+C | `0` |
| User error, such as a missing path or an unknown run name | `1` |
| Usage error, such as an unrecognised flag | `2` |
| `explore` stopped early by `--max-files`, `--timeout`, or one Ctrl+C | `3` |
| `explore` aborted by a second Ctrl+C, or `report` canceled part-built | `130` |

### Explore

The `explore` command will traverse through the file system located under the given path and continuously write information about the filesystem into a JSON file. All JSON files are located in the [`data/filesystem`](data/filesystem) folder.

While the scan runs, a live counter of files, elapsed time, size and throughput is redrawn in place. Pressing Ctrl+C once stops the scan and still writes what was gathered, flagged as a partial run. Pressing it a second time abandons the run and writes nothing.

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

Tests live under [`test/`](test/), split into four folders:

| Folder | Purpose |
|---|---|
| [`test/lint/`](test/lint/) | Confirms the codebase follows its own conventions |
| [`test/unit/`](test/unit/) | Confirms individual functions behave correctly in isolation |
| [`test/integration/`](test/integration/) | Confirms code integrates correctly with real systems such as the filesystem |
| [`test/end2end/`](test/end2end/) | Confirms real-world scenarios work correctly as a final safety net |

Useful flags:

```
pytest -v                              # verbose output
pytest test/unit/                      # unit tests only
pytest test/integration/               # integration tests only
pytest -k "format_bytes"               # run tests matching a name pattern
```

### End-to-end tests

The E2E suite drives the full pipeline — `explore` → `report` → `boot` — as a single session. It is excluded from the default `pytest` run and must be invoked explicitly:

```
pytest test/end2end/
```

The suite invokes `explore` and `report` as real subprocesses, starts the HTTP server in a background thread, runs assertions against all three stages, and deletes the `splora-e2e` run artifacts from `data/` on teardown.

## For Code Agents

The conventions that any AI agent — regardless of model or provider — must follow when working on this project live in [`agent/conventions.md`](agent/conventions.md). They cover the [`agent/`](agent/) workspace and its logging and notes requirements, the skills, the code style, and the test tiers. Read that file before making changes.

The [`.claude/`](.claude/) folder exists only for Claude Code's harness machinery compatibility reasons, and all its contents refers back to [`agent/`](agent/).
