from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

_REPO_ROOT    = Path(__file__).parent.parent
_FS_DIR       = _REPO_ROOT / "data" / "filesystem"
_TEMPLATE_DIR = _REPO_ROOT / "data" / "template"
_REPORT_DIR   = _REPO_ROOT / "data" / "report"
_VENDOR_DIR   = _REPO_ROOT / "vendor"

_TEMPLATE_FILES = ("index.html", "style.css", "script.js")
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _sanitize(s: str) -> str:
    return _UNSAFE.sub("_", s).strip(". ") or "unnamed"


def _latest_json(fs_dir: Path) -> Path | None:
    jsons = list(fs_dir.glob("*.json"))
    if not jsons:
        return None
    return max(jsons, key=lambda p: p.stat().st_mtime)


def report(args: argparse.Namespace) -> None:
    # ── Resolve source JSON ────────────────────────────────────────────────
    if args.name:
        json_path = _FS_DIR / f"{_sanitize(args.name)}.json"
        if not json_path.exists():
            print(f"Error: no run found for '{args.name}' ({json_path})", file=sys.stderr)
            sys.exit(1)
    else:
        json_path = _latest_json(_FS_DIR)
        if json_path is None:
            print("Error: no filesystem data found. Run 'splora explore' first.", file=sys.stderr)
            sys.exit(1)

    # ── Read JSON ──────────────────────────────────────────────────────────
    try:
        raw  = json_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: cannot read {json_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    meta = data.get("meta", {})

    # ── Build output directory ─────────────────────────────────────────────
    out_dir = _REPORT_DIR / json_path.stem   # stem is already sanitized by explore
    existed = out_dir.exists()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "vendor").mkdir(exist_ok=True)

    # ── Validate assets exist before copying ───────────────────────────────
    missing = [f for f in _TEMPLATE_FILES if not (_TEMPLATE_DIR / f).exists()]
    if not (_VENDOR_DIR / "echarts.min.js").exists():
        missing.append("vendor/echarts.min.js")
    if missing:
        print(f"Error: missing asset(s): {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # ── Copy template assets ───────────────────────────────────────────────
    for fname in _TEMPLATE_FILES:
        shutil.copy2(_TEMPLATE_DIR / fname, out_dir / fname)

    shutil.copy2(_VENDOR_DIR / "echarts.min.js", out_dir / "vendor" / "echarts.min.js")

    # ── Write data payload ─────────────────────────────────────────────────
    (out_dir / "data.json").write_text(raw, encoding="utf-8")

    # ── Summary ────────────────────────────────────────────────────────────
    verb = "Updated" if existed else "Generated"
    print(f"{verb}   : {meta.get('name', json_path.stem)}")
    if meta.get("partial"):
        print("Warning   : Partial scan — some files were not visited during explore.")
    print(f"  Root    : {meta.get('root', '?')}")
    print(f"  Files   : {meta.get('total_files', '?'):,}")
    print(f"  Output  : {out_dir}")
