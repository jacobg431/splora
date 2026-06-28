# Splora

Splora is a locally hosted, cross-platform file system data visualization tool.

The tool provides a web-based, interactive drill-down feature representing a file system, along with textual and graphical information about files and folders throughout the file system tree. That information includes disk usage, number of files located in each folder, distribution of file extensions, and distribution of file categories (i.e. Image, Source, Binary, etc.).

## Getting Started

### The Three Important Commands

Splora must first traverse and document the given file system, before generating the web-based report and showing it to the user. Each of these steps has its own command:

```
python splora.py explore <path-to-root-folder>
python splora.py report
python splora.py boot
```

### Explore

The `explore` command will traverse through the file system located under the given path and continously write information about the filesystem into a JSON file. All JSON files are located in the [`filesystem`](data/filesystem) folder.

This command can be run with the following options:
- `--name <exploration-run-name>` The title of the exploration run. Will be used both as file name for JSON file and as title in HTML report. If this option is not set, the title is the provided root folder name.
- `--depth <N>` Number of subdirectory levels to traverse through. If set to 0, it will attempt to traverse the whole file system tree, which is the default behavior.

### Report

The `report` command will generate a web-based report by using the files in [`template`](data/template) and the information given in the JSON file. All reports are located in the [`report`](data/report) folder.

This command can be run with the following options:
- `--name <exploration-run-name>` The JSON file name (without the `.json` extension) under [`filesystem`](data/filesystem) to use. If this option is not set, the last modified JSON file is selected.

### Boot

The `boot` command will open the generated report in the browser. 

This command can be run with the following options:
- `--name <exploration-run-name>` The report folder name under [`report`](data/report) to use. If this option is not set, the last generated report is selected.
