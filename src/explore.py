from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# ── Extension → category mapping ───────────────────────────────────────────

CATEGORIES: dict[str, str] = {
    # Image
    ".jpg": "Image",
    ".jpeg": "Image",
    ".png": "Image",
    ".gif": "Image",
    ".bmp": "Image",
    ".svg": "Image",
    ".webp": "Image",
    ".ico": "Image",
    ".tiff": "Image",
    ".tif": "Image",
    ".heic": "Image",
    ".avif": "Image",
    ".raw": "Image",
    # Video
    ".mp4": "Video",
    ".avi": "Video",
    ".mkv": "Video",
    ".mov": "Video",
    ".wmv": "Video",
    ".flv": "Video",
    ".webm": "Video",
    ".m4v": "Video",
    # Audio
    ".mp3": "Audio",
    ".wav": "Audio",
    ".flac": "Audio",
    ".aac": "Audio",
    ".ogg": "Audio",
    ".m4a": "Audio",
    ".wma": "Audio",
    # Document
    ".pdf": "Document",
    ".doc": "Document",
    ".docx": "Document",
    ".xls": "Document",
    ".xlsx": "Document",
    ".ppt": "Document",
    ".pptx": "Document",
    ".odt": "Document",
    ".ods": "Document",
    ".odp": "Document",
    # Source Code
    ".py": "Source Code",
    ".js": "Source Code",
    ".ts": "Source Code",
    ".java": "Source Code",
    ".c": "Source Code",
    ".cpp": "Source Code",
    ".h": "Source Code",
    ".hpp": "Source Code",
    ".cs": "Source Code",
    ".go": "Source Code",
    ".rs": "Source Code",
    ".rb": "Source Code",
    ".php": "Source Code",
    ".swift": "Source Code",
    ".kt": "Source Code",
    ".sh": "Source Code",
    ".bat": "Source Code",
    ".ps1": "Source Code",
    ".sql": "Source Code",
    ".r": "Source Code",
    ".lua": "Source Code",
    # Data
    ".json": "Data",
    ".csv": "Data",
    ".xml": "Data",
    ".yaml": "Data",
    ".yml": "Data",
    ".toml": "Data",
    ".db": "Data",
    ".sqlite": "Data",
    ".parquet": "Data",
    # Archive
    ".zip": "Archive",
    ".tar": "Archive",
    ".gz": "Archive",
    ".bz2": "Archive",
    ".7z": "Archive",
    ".rar": "Archive",
    ".xz": "Archive",
    # Executable
    ".exe": "Executable",
    ".dll": "Executable",
    ".so": "Executable",
    ".dylib": "Executable",
    ".bin": "Executable",
    ".app": "Executable",
    ".msi": "Executable",
    ".deb": "Executable",
    ".rpm": "Executable",
    # Font
    ".ttf": "Font",
    ".otf": "Font",
    ".woff": "Font",
    ".woff2": "Font",
    ".eot": "Font",
    # Config
    ".ini": "Config",
    ".cfg": "Config",
    ".conf": "Config",
    ".env": "Config",
    ".properties": "Config",
    ".editorconfig": "Config",
    ".gitignore": "Config",
}

# ── Paths ───────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).parent.parent
_FS_DIR = _REPO_ROOT / "data" / "filesystem"
_EXCLUDES_FILE = _REPO_ROOT / "data" / "config" / "default_excludes.txt"
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')

# ── Helpers ─────────────────────────────────────────────────────────────────


def _sanitize(s: str) -> str:
    """Strip characters that are invalid in file/folder names."""
    return _UNSAFE_CHARS.sub("_", s).strip(". ") or "unnamed"


def _load_default_excludes() -> set[str]:
    try:
        text = _EXCLUDES_FILE.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")}


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ── Traversal state ─────────────────────────────────────────────────────────


@dataclass
class _State:
    """Traversal limits and the visit count that decide when a scan stops."""

    files_visited: int = 0
    max_files: int | None = None
    deadline: float | None = None
    stopped: bool = False

    def check(self) -> bool:
        """Return True if traversal should stop now (time limit or already stopped)."""
        if self.stopped:
            return True
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.stopped = True
            return True
        return False

    def count_file(self) -> None:
        """Record one more file visited; set stopped if max_files is reached."""
        self.files_visited += 1
        if self.max_files is not None and self.files_visited >= self.max_files:
            self.stopped = True


# ── Core recursive scanner ──────────────────────────────────────────────────


def _scan_dir(
    path: Path,
    depth: int,
    depth_limit: int,
    excludes: set[str],
    state: _State,
) -> dict:
    node: dict = {
        "name": path.name or str(path),
        "path": str(path),
        "size": 0,
        "file_count": 0,
        "extensions": {},
        "categories": {},
        "children": [],
    }

    if state.check():
        return node

    try:
        entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
    except OSError:
        return node

    for entry in entries:
        if state.check():
            break

        try:
            is_file = entry.is_file(follow_symlinks=False)
            is_dir = entry.is_dir(follow_symlinks=False)
            is_junc = entry.is_junction()  # Windows NTFS junctions (always False on non-Windows)
        except OSError:
            continue

        if is_junc:
            continue

        if is_file:
            try:
                size = entry.stat(follow_symlinks=False).st_size
            except OSError:
                size = 0

            ext = Path(entry.name).suffix.lower()
            key = ext or "(none)"
            cat = CATEGORIES.get(ext, "Other")

            node["size"] += size
            node["file_count"] += 1
            node["extensions"][key] = node["extensions"].get(key, 0) + 1
            node["categories"][cat] = node["categories"].get(cat, 0) + 1
            state.count_file()

        elif is_dir:
            if entry.name in excludes:
                continue
            if depth_limit > 0 and depth >= depth_limit:
                continue

            child = _scan_dir(Path(entry.path), depth + 1, depth_limit, excludes, state)

            node["size"] += child["size"]
            node["file_count"] += child["file_count"]
            for k, v in child["extensions"].items():
                node["extensions"][k] = node["extensions"].get(k, 0) + v
            for k, v in child["categories"].items():
                node["categories"][k] = node["categories"].get(k, 0) + v
            node["children"].append(child)

    return node


# ── Argument helpers (extracted for unit testability) ───────────────────────


def _resolve_name(args: argparse.Namespace, root: Path) -> str:
    """Return the run name from CLI args, falling back to the root directory name."""
    root_label = root.name or re.sub(r"[\\/:]+", "", str(root.drive)) or "root"
    return args.name or root_label


def _build_excludes(args: argparse.Namespace) -> set[str]:
    """Merge user-supplied --exclude names with the built-in default list."""
    excludes: set[str] = set(args.exclude or [])
    if not getattr(args, "no_default_excludes", False):
        excludes |= _load_default_excludes()
    return excludes


def _build_state(args: argparse.Namespace) -> _State:
    """Construct a traversal _State from CLI args."""
    return _State(
        max_files=getattr(args, "max_files", None),
        deadline=(time.monotonic() + args.timeout) if getattr(args, "timeout", None) else None,
    )


# ── Public entry point ──────────────────────────────────────────────────────


def explore(args: argparse.Namespace) -> None:
    """Traverse a file system and record its structure as JSON."""
    root = Path(args.path).resolve()

    if not root.exists():
        print(f"Error: path does not exist: {root}", file=sys.stderr)
        sys.exit(1)
    if not root.is_dir():
        print(f"Error: not a directory: {root}", file=sys.stderr)
        sys.exit(1)

    raw_name = _resolve_name(args, root)
    safe_name = _sanitize(raw_name)
    excludes = _build_excludes(args)
    state = _build_state(args)

    _FS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _FS_DIR / f"{safe_name}.json"

    print(f"Exploring : {root}")
    if excludes:
        sample = ", ".join(sorted(excludes)[:5])
        extra = f" … (+{len(excludes) - 5} more)" if len(excludes) > 5 else ""
        print(f"Excluding : {sample}{extra}")

    t0 = time.monotonic()
    tree = _scan_dir(root, depth=0, depth_limit=args.depth, excludes=excludes, state=state)
    elapsed = time.monotonic() - t0

    output = {
        "meta": {
            "name": raw_name,
            "root": str(root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "partial": state.stopped,
            "total_size": tree["size"],
            "total_files": tree["file_count"],
            "elapsed_seconds": round(elapsed, 2),
        },
        "tree": tree,
    }

    # Write atomically: temp file → rename
    tmp_path = out_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(out_path)

    partial_note = " (partial — limit reached)" if state.stopped else ""
    print(f"\nDone{partial_note}.")
    print(f"  Files   : {state.files_visited:,}")
    print(f"  Size    : {_fmt_bytes(tree['size'])}")
    print(f"  Elapsed : {elapsed:.1f}s")
    print(f"  Output  : {out_path}")
