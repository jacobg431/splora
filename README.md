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

### Report

The `report` command will generate a web-based report by using the files in [`data/template`](data/template) and the information from a JSON file. All reports are located in the [`data/report`](data/report) folder. Reports are self-contained and work offline.

This command can be run with the following options:
- `--name <run-name>` The JSON file name (without the `.json` extension) under [`data/filesystem`](data/filesystem) to use. Defaults to the last modified JSON file.

### Boot

The `boot` command will open the generated report in the browser.

This command can be run with the following options:
- `--name <run-name>` The report folder name under [`data/report`](data/report) to open. Defaults to the last generated report.
