from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.command import Command
from src.escalation import Response
from src.outcome import EXIT_ERROR, EXIT_OK, NextStep, Outcome
from src.terminal import OutputConfig, notice_line

_REPO_ROOT = Path(__file__).parent.parent
_FS_DIR = _REPO_ROOT / "data" / "filesystem"
_TEMPLATE_DIR = _REPO_ROOT / "data" / "template"
_REPORT_DIR = _REPO_ROOT / "data" / "report"

_REQUIRED_TEMPLATE_FILES = ("index.html", "style.css", "main.js")
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')

# A report is staged as a sibling of its destination so the swap into place stays on one
# filesystem. The leading dot is what keeps boot from ever serving a staging directory.
_STAGING_PREFIX = "."
_STAGING_SUFFIX = ".tmp"


def _sanitize(s: str) -> str:
    return _UNSAFE.sub("_", s).strip(". ") or "unnamed"


def _latest_json(fs_dir: Path) -> Path | None:
    """Return the most recently modified .json file in fs_dir, or None if empty."""
    jsons = list(fs_dir.glob("*.json"))
    if not jsons:
        return None
    return max(jsons, key=lambda p: p.stat().st_mtime)


def _resolve_json_path(name: str | None, fs_dir: Path) -> Path:
    """Return the source JSON path for a run name, or the latest when none is given."""
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


def _read_json(path: Path) -> tuple[str, dict[str, Any]]:
    """Return a JSON file's raw text alongside its parsed content."""
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


def _staging_dir(out_dir: Path) -> Path:
    """Return the sibling directory a report is assembled in before it is swapped into place."""
    return out_dir.parent / f"{_STAGING_PREFIX}{out_dir.name}{_STAGING_SUFFIX}"


def _build_report(
    out_dir: Path,
    template_dir: Path,
    raw_json: str,
    on_swap: Callable[[], None] | None = None,
) -> None:
    """Assemble the report beside its destination and swap it in once it is complete."""
    staging = _staging_dir(out_dir)
    try:
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(template_dir, staging)
        (staging / "data.json").write_text(raw_json, encoding="utf-8")
        if on_swap is not None:
            on_swap()
        if out_dir.exists():
            shutil.rmtree(out_dir)
        staging.replace(out_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


class Report(Command):
    """The command that turns a recorded exploration run into an HTML report."""

    def __init__(self, args: argparse.Namespace, config: OutputConfig) -> None:
        self._args = args
        self._config = config
        self._swapping = False
        self._interrupted_while_swapping = False

    def run(self) -> Outcome:
        """Generate an HTML report from a recorded exploration run."""
        json_path = _resolve_json_path(self._args.name, _FS_DIR)
        raw, data = _read_json(json_path)
        meta = data.get("meta", {})

        missing = _missing_assets(_TEMPLATE_DIR)
        if missing:
            print(f"Error: missing asset(s): {', '.join(missing)}", file=sys.stderr)
            sys.exit(EXIT_ERROR)

        out_dir = _REPORT_DIR / json_path.stem
        existed = out_dir.exists()
        _build_report(out_dir, _TEMPLATE_DIR, raw, on_swap=self._entering_swap)
        self._swapping = False

        verb = "Updated" if existed else "Generated"
        print(f"{verb}   : {meta.get('name', json_path.stem)}")
        if meta.get("partial"):
            print("Warning   : Partial scan -- some files were not visited during explore.")
        print(f"  Root    : {meta.get('root', '?')}")
        print(f"  Files   : {meta.get('total_files', '?'):,}")
        print(f"  Output  : {out_dir}")
        if self._interrupted_while_swapping:
            print(notice_line("The report was already complete; it was kept.", config=self._config))
        return Outcome(code=EXIT_OK, next_step=NextStep(command="boot", name=json_path.stem))

    def cancel(self) -> Response:
        """Abandon the build, leaving any previous report untouched."""
        return self._stop()

    def abandon(self) -> Response:
        """Abandon the build, leaving any previous report untouched."""
        return self._stop()

    def _entering_swap(self) -> None:
        self._swapping = True

    def _stop(self) -> Response:
        if self._swapping:
            self._interrupted_while_swapping = True
            return Response.HANDLED
        print(notice_line("Canceled.", config=self._config))
        return Response.UNWIND
