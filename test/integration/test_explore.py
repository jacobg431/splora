"""Integration tests for src/explore.py."""

from __future__ import annotations

import argparse
import io
import json
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import pytest

import src.explore as explore_mod
from src.command import Command
from src.escalation import Abandon, Response
from src.explore import Explore, _scan_dir, _State
from src.outcome import EXIT_OK, EXIT_PARTIAL, Outcome
from src.progress import Progress
from src.terminal import OutputConfig

_TRIMMED = OutputConfig(trim=True, use_color=False)
_DECORATED = OutputConfig(trim=False, use_color=False)
_REAL_SCAN_DIR = explore_mod._scan_dir


def _quiet() -> Progress:
    return Progress(io.StringIO(), use_color=False)


def _make_scan_tree(parent: Path) -> Path:
    """Create a directory of files to scan, kept a sibling of the output directory."""
    scan = parent / "scan"
    scan.mkdir()
    for name in ("a.txt", "b.py", "c.json"):
        (scan / name).write_bytes(b"x" * 10)
    return scan


def _scan_calling(*responses: Callable[[], object]) -> Callable[..., dict[str, object]]:
    """Return a _scan_dir stand-in that invokes the given responses before it scans."""

    def scan(*args: Any, **kwargs: Any) -> dict[str, Any]:
        for respond in responses:
            respond()
        return _REAL_SCAN_DIR(*args, **kwargs)

    return scan


def _advancing_clock(step: float = 1.0) -> Callable[[], float]:
    """Return a time.monotonic() stand-in that advances by `step` seconds per call."""
    now = 0.0

    def monotonic() -> float:
        nonlocal now
        value = now
        now += step
        return value

    return monotonic


def _replace_calling(respond: Callable[[], object]) -> Callable[..., None]:
    """Return a Path.replace stand-in that invokes a response instead of renaming."""

    def replace(_self: object, _target: object) -> None:
        respond()

    return replace


class _JsonCalling:
    """A stand-in for the json module that invokes a response before it serialises."""

    def __init__(self, *responses: Callable[[], object]) -> None:
        self._responses = responses

    def dumps(self, *args: Any, **kwargs: Any) -> str:
        """Invoke every response, then serialise exactly as the real module would."""
        for respond in self._responses:
            respond()
        return json.dumps(*args, **kwargs)


def _args(**kwargs: Any) -> argparse.Namespace:
    """Build an argparse.Namespace with sensible test defaults."""
    defaults: dict[str, Any] = {
        "path": None,
        "name": None,
        "depth": 0,
        "max_files": None,
        "timeout": None,
        "exclude": [],
        "no_default_excludes": True,  # isolate from real config file
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _patch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect _FS_DIR to an output directory and return it."""
    out_dir = tmp_path / "output"
    monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)
    return out_dir


class TestExploreCommand:
    """The explore command traversing a tree and writing its JSON."""

    def test_generates_valid_json_with_correct_structure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        # Keep scan_dir and out_dir as siblings so out_dir is never included in the scan.
        scan_dir = tmp_path / "scan"
        scan_dir.mkdir()
        (scan_dir / "file.txt").write_bytes(b"hello")
        (scan_dir / "script.py").write_bytes(b"code")
        sub = scan_dir / "subdir"
        sub.mkdir()
        (sub / "data.json").write_bytes(b"{}")

        out_dir = _patch(monkeypatch, tmp_path)

        Explore(_args(path=str(scan_dir), name="test-run"), _TRIMMED).run()

        data = load_json(out_dir / "test-run.json")

        assert data["meta"]["name"] == "test-run"
        assert data["meta"]["root"] == str(scan_dir)
        assert data["meta"]["partial"] is False
        assert data["meta"]["total_files"] == 3
        assert data["tree"]["file_count"] == 3
        assert len(data["tree"]["children"]) == 1
        assert data["tree"]["children"][0]["name"] == "subdir"

    def test_name_defaults_to_root_folder_name(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        (tmp_path / "file.txt").write_bytes(b"x")

        out_dir = _patch(monkeypatch, tmp_path)

        Explore(_args(path=str(tmp_path)), _TRIMMED).run()  # no explicit name

        data = load_json(out_dir / f"{tmp_path.name}.json")
        assert data["meta"]["name"] == tmp_path.name

    def test_total_size_is_accurate(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        (tmp_path / "small.bin").write_bytes(b"x" * 100)
        (tmp_path / "large.bin").write_bytes(b"y" * 900)

        out_dir = _patch(monkeypatch, tmp_path)

        Explore(_args(path=str(tmp_path), name="size-run"), _TRIMMED).run()

        data = load_json(out_dir / "size-run.json")
        assert data["meta"]["total_size"] == 1000

    def test_marks_partial_when_max_files_reached(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_bytes(b"x")

        out_dir = _patch(monkeypatch, tmp_path)

        Explore(_args(path=str(tmp_path), name="partial-run", max_files=5), _TRIMMED).run()

        data = load_json(out_dir / "partial-run.json")
        assert data["meta"]["partial"] is True
        assert data["meta"]["total_files"] <= 5

    def test_marks_partial_when_timeout_expires(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        scan = _make_scan_tree(tmp_path)
        out_dir = _patch(monkeypatch, tmp_path)
        monkeypatch.setattr(time, "monotonic", _advancing_clock())

        Explore(_args(path=str(scan), name="timeout-run", timeout=0.0001), _TRIMMED).run()

        data = load_json(out_dir / "timeout-run.json")
        assert data["meta"]["partial"] is True

    def test_respects_exclude_list(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        keep = tmp_path / "keep"
        keep.mkdir()
        (keep / "file.txt").write_bytes(b"x")

        skip = tmp_path / "node_modules"
        skip.mkdir()
        (skip / "big.js").write_bytes(b"y" * 1000)

        out_dir = _patch(monkeypatch, tmp_path)

        Explore(_args(path=str(tmp_path), name="exc-run", exclude=["node_modules"]), _TRIMMED).run()

        data = load_json(out_dir / "exc-run.json")
        assert data["meta"]["total_files"] == 1
        child_names = [c["name"] for c in data["tree"]["children"]]
        assert "node_modules" not in child_names
        assert "keep" in child_names

    def test_depth_limit_prevents_deep_traversal(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        # root/a/b/c/deep.txt is 3 levels deep; root/a/shallow.txt is 1 level deep
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_bytes(b"deep")
        (tmp_path / "a" / "shallow.txt").write_bytes(b"shallow")

        out_dir = _patch(monkeypatch, tmp_path)

        # depth=2: root(0) → a(1) → b(2) → c is at depth 2 so NOT entered
        Explore(_args(path=str(tmp_path), name="depth-run", depth=2), _TRIMMED).run()

        data = load_json(out_dir / "depth-run.json")
        assert data["meta"]["total_files"] == 1  # only shallow.txt

    def test_extension_and_category_distribution_in_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        (tmp_path / "photo.jpg").write_bytes(b"img")
        (tmp_path / "code.py").write_bytes(b"src")
        (tmp_path / "archive.zip").write_bytes(b"zip")

        out_dir = _patch(monkeypatch, tmp_path)

        Explore(_args(path=str(tmp_path), name="cat-run"), _TRIMMED).run()

        data = load_json(out_dir / "cat-run.json")
        tree = data["tree"]
        assert tree["extensions"][".jpg"] == 1
        assert tree["extensions"][".py"] == 1
        assert tree["extensions"][".zip"] == 1
        assert tree["categories"]["Image"] == 1
        assert tree["categories"]["Source Code"] == 1
        assert tree["categories"]["Archive"] == 1

    def test_output_file_is_not_written_as_partial_tmp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "file.txt").write_bytes(b"x")

        out_dir = _patch(monkeypatch, tmp_path)

        Explore(_args(path=str(tmp_path), name="atomic-run"), _TRIMMED).run()

        # The .tmp file should have been renamed away; only the final .json remains
        assert (out_dir / "atomic-run.json").exists()
        assert not (out_dir / "atomic-run.tmp").exists()

    def test_child_stats_are_aggregated_to_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "a.py").write_bytes(b"x" * 50)
        (tmp_path / "b.txt").write_bytes(b"y" * 50)

        out_dir = _patch(monkeypatch, tmp_path)

        Explore(_args(path=str(tmp_path), name="agg-run"), _TRIMMED).run()

        data = load_json(out_dir / "agg-run.json")
        assert data["tree"]["size"] == 100
        assert data["tree"]["file_count"] == 2
        # .py is Source Code; .txt is Other — both should appear at root level
        assert "Source Code" in data["tree"]["categories"]
        assert "Other" in data["tree"]["categories"]


class TestScanDir:
    """Recursive directory scanning and aggregation of child statistics."""

    def test_empty_directory_returns_zero_counts(self, tmp_path: Path) -> None:
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["file_count"] == 0
        assert node["size"] == 0
        assert node["children"] == []
        assert node["extensions"] == {}
        assert node["categories"] == {}

    def test_node_carries_correct_name_and_path(self, tmp_path: Path) -> None:
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["name"] == tmp_path.name
        assert node["path"] == str(tmp_path)

    def test_counts_files_and_accumulates_size(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_bytes(b"hello")  # 5 bytes
        (tmp_path / "b.txt").write_bytes(b"world!")  # 6 bytes
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["file_count"] == 2
        assert node["size"] == 11

    def test_recurses_and_aggregates_child_stats(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "code.py").write_bytes(b"x" * 100)
        (tmp_path / "readme.txt").write_bytes(b"y" * 200)
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["file_count"] == 2
        assert node["size"] == 300
        assert len(node["children"]) == 1
        assert node["children"][0]["name"] == "sub"

    def test_assigns_correct_extension_keys(self, tmp_path: Path) -> None:
        (tmp_path / "image.jpg").write_bytes(b"img")
        (tmp_path / "script.py").write_bytes(b"code")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["extensions"][".jpg"] == 1
        assert node["extensions"][".py"] == 1

    def test_assigns_correct_categories(self, tmp_path: Path) -> None:
        (tmp_path / "image.jpg").write_bytes(b"img")
        (tmp_path / "script.py").write_bytes(b"code")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["categories"]["Image"] == 1
        assert node["categories"]["Source Code"] == 1

    def test_no_extension_uses_none_key(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_bytes(b"make")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["extensions"]["(none)"] == 1
        assert node["categories"]["Other"] == 1

    def test_unknown_extension_maps_to_other(self, tmp_path: Path) -> None:
        (tmp_path / "file.splora").write_bytes(b"x")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["categories"]["Other"] == 1

    def test_respects_exclude_list(self, tmp_path: Path) -> None:
        ignored = tmp_path / "node_modules"
        ignored.mkdir()
        (ignored / "big.js").write_bytes(b"x" * 1000)
        node = _scan_dir(
            tmp_path,
            depth=0,
            depth_limit=0,
            excludes={"node_modules"},
            state=_State(),
            progress=_quiet(),
        )
        assert node["file_count"] == 0
        assert node["children"] == []

    def test_respects_depth_limit(self, tmp_path: Path) -> None:
        # Structure: root/a/b/deep.txt — depth_limit=1 means we enter 'a' but not 'b'
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_bytes(b"too deep")
        (tmp_path / "a" / "shallow.txt").write_bytes(b"ok")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=1, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["file_count"] == 1  # only shallow.txt

    def test_unlimited_depth_traverses_all_levels(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "file.txt").write_bytes(b"deep")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["file_count"] == 1

    def test_stops_early_on_max_files(self, tmp_path: Path) -> None:
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_bytes(b"x")
        state = _State(max_files=4)
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=state, progress=_quiet()
        )
        assert node["file_count"] <= 4
        assert state.stopped

    def test_children_are_sorted_alphabetically(self, tmp_path: Path) -> None:
        for name in ("zebra", "alpha", "middle"):
            (tmp_path / name).mkdir()
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        names = [c["name"] for c in node["children"]]
        assert names == sorted(names)

    def test_skips_symlinks_to_files(self, tmp_path: Path) -> None:
        real = tmp_path / "real.txt"
        real.write_bytes(b"content")
        try:
            link = tmp_path / "link.txt"
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["file_count"] == 1  # only the real file

    def test_skips_symlinks_to_directories(self, tmp_path: Path) -> None:
        real_dir = tmp_path / "real_dir"
        real_dir.mkdir()
        (real_dir / "file.txt").write_bytes(b"content")
        try:
            link_dir = tmp_path / "link_dir"
            link_dir.symlink_to(real_dir)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        # file.txt inside real_dir is counted; link_dir is skipped entirely
        assert node["file_count"] == 1


class TestExitCodes:
    """The code a completed scan reports, and the step it points at next."""

    def test_a_whole_scan_succeeds(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        scan = _make_scan_tree(tmp_path)
        _patch(monkeypatch, tmp_path)
        assert Explore(_args(path=str(scan), name="whole"), _TRIMMED).run().code == EXIT_OK

    def test_stopping_on_max_files_is_partial(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scan = _make_scan_tree(tmp_path)
        _patch(monkeypatch, tmp_path)
        outcome = Explore(_args(path=str(scan), name="capped", max_files=1), _TRIMMED).run()
        assert outcome.code == EXIT_PARTIAL

    def test_stopping_on_timeout_is_partial(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scan = _make_scan_tree(tmp_path)
        _patch(monkeypatch, tmp_path)
        monkeypatch.setattr(time, "monotonic", _advancing_clock())
        command = Explore(_args(path=str(scan), name="timed", timeout=0.0001), _TRIMMED)
        assert command.run().code == EXIT_PARTIAL

    def test_a_whole_scan_points_at_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scan = _make_scan_tree(tmp_path)
        _patch(monkeypatch, tmp_path)
        outcome = Explore(_args(path=str(scan), name="whole"), _TRIMMED).run()
        assert outcome.next_step is not None
        assert outcome.next_step.command == "report"

    def test_the_next_step_names_the_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scan = _make_scan_tree(tmp_path)
        _patch(monkeypatch, tmp_path)
        outcome = Explore(_args(path=str(scan), name="named-run"), _TRIMMED).run()
        assert outcome.next_step is not None
        assert outcome.next_step.name == "named-run"

    def test_a_capped_scan_still_points_at_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scan = _make_scan_tree(tmp_path)
        _patch(monkeypatch, tmp_path)
        outcome = Explore(_args(path=str(scan), name="capped", max_files=1), _TRIMMED).run()
        assert outcome.next_step is not None

    def test_a_capped_scan_says_the_limit_was_reached(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        scan = _make_scan_tree(tmp_path)
        _patch(monkeypatch, tmp_path)
        Explore(_args(path=str(scan), name="capped", max_files=1), _TRIMMED).run()
        assert "Done (partial -- limit reached)." in capsys.readouterr().out


class TestCancelledScan:
    """A first Ctrl+C, which stops the scan and keeps what it has already found."""

    def _cancelled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: OutputConfig = _TRIMMED
    ) -> tuple[Outcome, Path]:
        scan = _make_scan_tree(tmp_path)
        out_dir = _patch(monkeypatch, tmp_path)
        command = Explore(_args(path=str(scan), name="stopped"), config)
        monkeypatch.setattr(explore_mod, "_scan_dir", _scan_calling(command.cancel))
        return command.run(), out_dir / "stopped.json"

    def test_it_reports_a_partial_scan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outcome, _ = self._cancelled(tmp_path, monkeypatch)
        assert outcome.code == EXIT_PARTIAL

    def test_it_writes_the_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _, json_path = self._cancelled(tmp_path, monkeypatch)
        assert json_path.exists()

    def test_it_flags_the_output_partial(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        _, json_path = self._cancelled(tmp_path, monkeypatch)
        assert load_json(json_path)["meta"]["partial"] is True

    def test_it_still_points_at_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outcome, _ = self._cancelled(tmp_path, monkeypatch)
        assert outcome.next_step is not None
        assert outcome.next_step.command == "report"

    def test_it_says_the_scan_stopped_early(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._cancelled(tmp_path, monkeypatch)
        assert "Done (partial -- stopped early)." in capsys.readouterr().out

    def test_it_promises_the_partial_will_be_saved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._cancelled(tmp_path, monkeypatch)
        assert "the partial scan will be saved" in capsys.readouterr().out

    def test_it_names_what_a_further_press_would_do(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._cancelled(tmp_path, monkeypatch)
        assert "Press Ctrl+C again to discard it." in capsys.readouterr().out

    def test_the_decorated_notice_carries_a_glyph(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._cancelled(tmp_path, monkeypatch, config=_DECORATED)
        assert "! Stopping;" in capsys.readouterr().out


class TestInterruptedCommit:
    """A Ctrl+C arriving once the scan is over, while its result is being written."""

    def _pressed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        *responses: str,
        config: OutputConfig = _TRIMMED,
    ) -> tuple[Explore, Path]:
        scan = _make_scan_tree(tmp_path)
        out_dir = _patch(monkeypatch, tmp_path)
        command = Explore(_args(path=str(scan), name="saved"), config)
        monkeypatch.setattr(
            explore_mod, "json", _JsonCalling(*(getattr(command, name) for name in responses))
        )
        return command, out_dir / "saved.json"

    def test_a_cancel_lets_the_write_finish(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        command, json_path = self._pressed(tmp_path, monkeypatch, "cancel")
        command.run()
        assert load_json(json_path)["meta"]["total_files"] == 3

    def test_a_cancel_leaves_the_run_successful(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        command, _ = self._pressed(tmp_path, monkeypatch, "cancel")
        assert command.run().code == EXIT_OK

    def test_a_cancel_does_not_mark_the_scan_partial(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        load_json: Callable[[Path], dict[str, Any]],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        command, json_path = self._pressed(tmp_path, monkeypatch, "cancel")
        command.run()
        assert load_json(json_path)["meta"]["partial"] is False
        assert "Done." in capsys.readouterr().out

    def test_a_cancel_says_the_scan_is_being_saved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        command, _ = self._pressed(tmp_path, monkeypatch, "cancel")
        command.run()
        assert "Saving the scan; press Ctrl+C again to discard it." in capsys.readouterr().out

    def _pressed_to_abandon(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        press: Callable[[int], None],
        config: OutputConfig = _TRIMMED,
    ) -> tuple[Explore, Path]:
        scan = _make_scan_tree(tmp_path)
        out_dir = _patch(monkeypatch, tmp_path)
        command = Explore(_args(path=str(scan), name="saved"), config)
        monkeypatch.setattr(explore_mod, "json", _JsonCalling(lambda: press(2)))
        return command, out_dir / "saved.json"

    def test_an_abandon_discards_the_write(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
    ) -> None:
        command, json_path = self._pressed_to_abandon(tmp_path, monkeypatch, press)
        with escalating_run(command):
            with pytest.raises(Abandon):
                command.run()
        assert not json_path.exists()

    def test_an_abandon_leaves_no_partial_file_behind(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
    ) -> None:
        command, json_path = self._pressed_to_abandon(tmp_path, monkeypatch, press)
        with escalating_run(command):
            with pytest.raises(Abandon):
                command.run()
        assert list(json_path.parent.glob("*.tmp")) == []

    def test_an_abandon_after_the_write_removes_the_temp_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
    ) -> None:
        scan = _make_scan_tree(tmp_path)
        out_dir = _patch(monkeypatch, tmp_path)
        command = Explore(_args(path=str(scan), name="saved"), _TRIMMED)
        monkeypatch.setattr(Path, "replace", _replace_calling(lambda: press(2)))
        with escalating_run(command):
            with pytest.raises(Abandon):
                command.run()
        assert list(out_dir.glob("*.tmp")) == []
        assert not (out_dir / "saved.json").exists()


class TestAbandonedScan:
    """A second Ctrl+C, which discards the scan outright."""

    def _abandoned(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
        config: OutputConfig = _TRIMMED,
    ) -> Path:
        scan = _make_scan_tree(tmp_path)
        out_dir = _patch(monkeypatch, tmp_path)
        command = Explore(_args(path=str(scan), name="stopped"), config)
        monkeypatch.setattr(explore_mod, "_scan_dir", _scan_calling(lambda: press(2)))
        with escalating_run(command):
            with pytest.raises(Abandon):
                command.run()
        return out_dir / "stopped.json"

    def test_it_writes_nothing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
    ) -> None:
        json_path = self._abandoned(tmp_path, monkeypatch, escalating_run, press)
        assert not json_path.exists()

    def test_it_leaves_no_partial_file_behind(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
    ) -> None:
        json_path = self._abandoned(tmp_path, monkeypatch, escalating_run, press)
        assert list(json_path.parent.glob("*.tmp")) == []

    def test_it_says_the_scan_was_discarded(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._abandoned(tmp_path, monkeypatch, escalating_run, press)
        assert "Discarded; no scan was saved." in capsys.readouterr().out

    def test_the_trimmed_notice_is_the_bare_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._abandoned(tmp_path, monkeypatch, escalating_run, press)
        assert capsys.readouterr().out.splitlines()[-1] == "Discarded; no scan was saved."

    def test_the_decorated_notice_carries_a_glyph(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._abandoned(tmp_path, monkeypatch, escalating_run, press, config=_DECORATED)
        assert capsys.readouterr().out.splitlines()[-1] == "! Discarded; no scan was saved."


def _explore_scanning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Explore:
    scan = _make_scan_tree(tmp_path)
    _patch(monkeypatch, tmp_path)
    return Explore(_args(path=str(scan), name="phase-run"), _TRIMMED)


def _explore_committing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Explore:
    command = _explore_scanning(tmp_path, monkeypatch)
    command._committing = True
    return command


_CASES = [
    pytest.param(
        _explore_scanning,
        "cancel",
        Response.HANDLED,
        "the partial scan will be saved",
        id="scanning/cancel",
    ),
    pytest.param(
        _explore_scanning,
        "abandon",
        Response.UNWIND,
        "Discarded; no scan was saved.",
        id="scanning/abandon",
    ),
    pytest.param(
        _explore_committing, "cancel", Response.HANDLED, "Saving the scan", id="committing/cancel"
    ),
    pytest.param(
        _explore_committing,
        "abandon",
        Response.UNWIND,
        "Discarded; no scan was saved.",
        id="committing/abandon",
    ),
]


class TestInterruptResponse:
    """What cancel() and abandon() answer and print, in each phase."""

    @pytest.mark.parametrize("make_command, action, expected, notice", _CASES)
    def test_interrupt_response(
        self,
        make_command: Callable[..., Explore],
        action: str,
        expected: Response,
        notice: str | None,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        assert_interrupt_response: Callable[..., None],
    ) -> None:
        command = make_command(tmp_path, monkeypatch)
        assert_interrupt_response(command, action, expected, notice)
