"""End-to-end tests for what the commands print and the codes they exit with."""

from __future__ import annotations

from pathlib import Path

from src.banner import TAGLINE

_ESCAPE = b"\x1b["


def _make_tree(root: Path) -> Path:
    """Create a small tree to scan, kept apart from anything the run writes."""
    scan = root / "scan"
    scan.mkdir()
    (scan / "main.py").write_bytes(b"print('hi')")
    (scan / "notes.txt").write_bytes(b"words")
    return scan


class TestDecoratedOutput:
    """What a run prints when nothing is trimmed away."""

    def test_the_banner_is_printed(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        result = attempt_cli("explore", str(scan), "--name", scratch_run("decorated"))
        assert TAGLINE.encode() in result.stdout

    def test_the_next_step_is_printed(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        name = scratch_run("advice")
        result = attempt_cli("explore", str(scan), "--name", name)
        assert f"splora report --name {name}".encode() in result.stdout

    def test_a_whole_scan_exits_zero(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        result = attempt_cli("explore", str(scan), "--name", scratch_run("clean"))
        assert result.returncode == 0


class TestTrimmedOutput:
    """What survives when the decorations are suppressed."""

    def test_the_banner_is_suppressed(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        name = scratch_run("trimmed")
        result = attempt_cli("explore", str(scan), "--name", name, "--trim-output")
        assert TAGLINE.encode() not in result.stdout

    def test_the_next_step_is_suppressed(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        name = scratch_run("trimmed-advice")
        result = attempt_cli("explore", str(scan), "--name", name, "--trim-output")
        assert b"Next:" not in result.stdout

    def test_the_result_summary_survives(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        name = scratch_run("trimmed-summary")
        result = attempt_cli("explore", str(scan), "--name", name, "--trim-output")
        assert b"Done." in result.stdout
        assert b"Files   :" in result.stdout

    def test_a_report_keeps_its_summary(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        name = scratch_run("trimmed-report")
        attempt_cli("explore", str(scan), "--name", name, "--trim-output")
        result = attempt_cli("report", "--name", name, "--trim-output")
        assert b"Generated" in result.stdout
        assert TAGLINE.encode() not in result.stdout


class TestExitCodes:
    """The codes the commands hand back to a shell."""

    def test_a_capped_scan_reports_partial(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        name = scratch_run("capped")
        result = attempt_cli("explore", str(scan), "--name", name, "--max-files", "1")
        assert result.returncode == 3

    def test_a_missing_path_is_a_user_error(self, attempt_cli, tmp_path, scratch_run):
        result = attempt_cli("explore", str(tmp_path / "absent"), "--name", scratch_run("absent"))
        assert result.returncode == 1

    def test_a_flag_before_its_subcommand_is_a_usage_error(self, attempt_cli, tmp_path):
        result = attempt_cli("--trim-output", "explore", str(tmp_path))
        assert result.returncode == 2

    def test_an_unknown_report_is_a_user_error(self, attempt_cli, scratch_run):
        result = attempt_cli("report", "--name", "no-such-run-exists")
        assert result.returncode == 1


class TestRedirectedOutput:
    """What reaches a pipe, where the locale encoding decides what can be written."""

    def test_every_byte_of_a_scan_is_ascii(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        result = attempt_cli("explore", str(scan), "--name", scratch_run("ascii"))
        assert result.stdout.isascii()
        assert result.stderr.isascii()

    def test_every_byte_of_a_report_is_ascii(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        name = scratch_run("ascii-report")
        attempt_cli("explore", str(scan), "--name", name)
        result = attempt_cli("report", "--name", name)
        assert result.stdout.isascii()

    def test_a_partial_scan_is_ascii(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        name = scratch_run("ascii-partial")
        result = attempt_cli("explore", str(scan), "--name", name, "--max-files", "1")
        assert result.stdout.isascii()

    def test_no_escape_sequence_reaches_a_pipe(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        result = attempt_cli("explore", str(scan), "--name", scratch_run("nocolor"))
        assert _ESCAPE not in result.stdout

    def test_no_progress_line_reaches_a_pipe(self, attempt_cli, tmp_path, scratch_run):
        scan = _make_tree(tmp_path)
        result = attempt_cli("explore", str(scan), "--name", scratch_run("noprogress"))
        assert b"Scanning:" not in result.stderr
