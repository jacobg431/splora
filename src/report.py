from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_FS_DIR = _REPO_ROOT / "data" / "filesystem"
_TEMPLATE_DIR = _REPO_ROOT / "data" / "template"
_REPORT_DIR = _REPO_ROOT / "data" / "report"

_REQUIRED_TEMPLATE_FILES = ("index.html", "style.css", "main.js")
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _sanitize(s: str) -> str:
    return _UNSAFE.sub("_", s).strip(". ") or "unnamed"


def _latest_json(fs_dir: Path) -> Path | None:
    """Return the most recently modified .json file in fs_dir, or None if empty."""
    jsons = list(fs_dir.glob("*.json"))
    if not jsons:
        return None
    return max(jsons, key=lambda p: p.stat().st_mtime)


def _resolve_json_path(name: str | None, fs_dir: Path) -> Path:
    """Return the source JSON Path for a given run name (or the latest if None).

    Exits with code 1 if the file cannot be found.
    """
    if name:
        path = fs_dir / f"{_sanitize(name)}.json"
        if not path.exists():
            print(f"Error: no run found for '{name}' ({path})", file=sys.stderr)
            sys.exit(1)
        return path
    latest = _latest_json(fs_dir)
    if latest is None:
        print("Error: no filesystem data found. Run 'splora explore' first.", file=sys.stderr)
        sys.exit(1)
    return latest


def _read_json(path: Path) -> tuple[str, dict]:
    """Read and parse a JSON file; return (raw_text, parsed_dict).

    Exits with code 1 on I/O or parse errors.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: cannot read {path}: {exc}", file=sys.stderr)
        sys.exit(1)
    return raw, data


def _missing_assets(template_dir: Path) -> list[str]:
    """Return a list of required template files that are absent."""
    return [f for f in _REQUIRED_TEMPLATE_FILES if not (template_dir / f).exists()]


def _build_report(out_dir: Path, template_dir: Path, raw_json: str) -> None:
    """Create the report directory tree and write all output files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template_dir, out_dir, dirs_exist_ok=True)
    (out_dir / "data.json").write_text(raw_json, encoding="utf-8")


def report(args: argparse.Namespace) -> None:
    json_path = _resolve_json_path(args.name, _FS_DIR)
    raw, data = _read_json(json_path)
    meta = data.get("meta", {})

    missing = _missing_assets(_TEMPLATE_DIR)
    if missing:
        print(f"Error: missing asset(s): {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    out_dir = _REPORT_DIR / json_path.stem
    existed = out_dir.exists()
    _build_report(out_dir, _TEMPLATE_DIR, raw)

    verb = "Updated" if existed else "Generated"
    print(f"{verb}   : {meta.get('name', json_path.stem)}")
    if meta.get("partial"):
        print("Warning   : Partial scan — some files were not visited during explore.")
    print(f"  Root    : {meta.get('root', '?')}")
    print(f"  Files   : {meta.get('total_files', '?'):,}")
    print(f"  Output  : {out_dir}")
