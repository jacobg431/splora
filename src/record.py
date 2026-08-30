from __future__ import annotations

from typing import TypedDict


class ScanNode(TypedDict):
    """One directory in the scan tree, with its aggregated child statistics."""

    name: str
    path: str
    size: int
    file_count: int
    extensions: dict[str, int]
    categories: dict[str, int]
    children: list[ScanNode]


class ScanMeta(TypedDict):
    """The summary block a recorded scan carries alongside its tree."""

    name: str
    root: str
    generated_at: str
    partial: bool
    total_size: int
    total_files: int
    elapsed_seconds: float


class Record(TypedDict):
    """A complete recorded scan: its metadata and the tree it produced."""

    meta: ScanMeta
    tree: ScanNode
