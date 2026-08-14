"""End-to-end tests for the full Splora pipeline: explore → report → boot.

Run with:
    pytest test/end2end/

These tests are excluded from the default `pytest` run (testpaths in
pyproject.toml covers only test/unit and test/integration).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from src.report import _TEMPLATE_DIR


# ── explore ────────────────────────────────────────────────────────────────


class TestExplore:
    def test_json_file_is_created(self, e2e_pipeline):
        assert e2e_pipeline["json_path"].exists()

    def test_json_is_not_partial(self, e2e_pipeline):
        data = json.loads(e2e_pipeline["json_path"].read_text(encoding="utf-8"))
        assert data["meta"]["partial"] is False

    def test_run_name_matches(self, e2e_pipeline):
        data = json.loads(e2e_pipeline["json_path"].read_text(encoding="utf-8"))
        assert data["meta"]["name"] == e2e_pipeline["run_name"]

    def test_root_path_matches_scan_directory(self, e2e_pipeline):
        data = json.loads(e2e_pipeline["json_path"].read_text(encoding="utf-8"))
        assert data["meta"]["root"] == str(e2e_pipeline["scan_root"])

    def test_total_file_count_is_correct(self, e2e_pipeline):
        data = json.loads(e2e_pipeline["json_path"].read_text(encoding="utf-8"))
        assert data["meta"]["total_files"] == 5

    def test_tree_has_one_subdirectory(self, e2e_pipeline):
        data = json.loads(e2e_pipeline["json_path"].read_text(encoding="utf-8"))
        assert len(data["tree"]["children"]) == 1
        assert data["tree"]["children"][0]["name"] == "subdir"

    def test_extension_distribution_is_correct(self, e2e_pipeline):
        data = json.loads(e2e_pipeline["json_path"].read_text(encoding="utf-8"))
        exts = data["tree"]["extensions"]
        assert exts.get(".py") == 1
        assert exts.get(".txt") == 1
        assert exts.get(".png") == 1
        assert exts.get(".json") == 1
        assert exts.get(".mp4") == 1

    def test_category_distribution_is_correct(self, e2e_pipeline):
        data = json.loads(e2e_pipeline["json_path"].read_text(encoding="utf-8"))
        cats = data["tree"]["categories"]
        assert cats.get("Source Code") == 1
        assert cats.get("Other") == 1  # .txt
        assert cats.get("Image") == 1
        assert cats.get("Data") == 1
        assert cats.get("Video") == 1

    def test_total_size_matches_actual_files(self, e2e_pipeline):
        data = json.loads(e2e_pipeline["json_path"].read_text(encoding="utf-8"))
        # Sum up the sizes of all files we created in _build_scan_tree
        expected = (
            len(b"print('hello')")  # main.py
            + len(b"Splora end-to-end test")  # readme.txt
            + len(b"\x89PNG" + b"\x00" * 96)  # image.png
            + len(b'{"key": "value"}')  # data.json
            + 200  # video.mp4
        )
        assert data["meta"]["total_size"] == expected


# ── report ─────────────────────────────────────────────────────────────────


class TestReport:
    def test_report_directory_exists(self, e2e_pipeline):
        assert e2e_pipeline["report_dir"].is_dir()

    def test_all_required_files_are_present(self, e2e_pipeline):
        d = e2e_pipeline["report_dir"]
        for fname in ("index.html", "style.css", "main.js", "data.json"):
            assert (d / fname).exists(), f"Missing: {fname}"

    def test_data_json_content_matches_filesystem_json(self, e2e_pipeline):
        src = e2e_pipeline["json_path"].read_text(encoding="utf-8")
        dst = (e2e_pipeline["report_dir"] / "data.json").read_text(encoding="utf-8")
        assert src == dst

    def test_index_html_references_required_assets(self, e2e_pipeline):
        html = (e2e_pipeline["report_dir"] / "index.html").read_text(encoding="utf-8")
        assert "style.css" in html
        assert "main.js" in html

    def test_no_extra_files_in_report_root(self, e2e_pipeline):
        # The report root mirrors the template tree plus the generated data.json.
        top = {p.name for p in e2e_pipeline["report_dir"].iterdir()}
        template_top = {p.name for p in _TEMPLATE_DIR.iterdir()}
        assert top == template_top | {"data.json"}


# ── boot ───────────────────────────────────────────────────────────────────


class TestBoot:
    def test_server_responds_with_200(self, e2e_pipeline):
        resp = urllib.request.urlopen(e2e_pipeline["url"], timeout=5)
        assert resp.status == 200

    def test_index_html_is_served(self, e2e_pipeline):
        body = urllib.request.urlopen(e2e_pipeline["url"], timeout=5).read().decode()
        assert "<html" in body.lower()

    def test_stylesheet_is_served(self, e2e_pipeline):
        resp = urllib.request.urlopen(e2e_pipeline["url"] + "style.css", timeout=5)
        assert resp.status == 200

    def test_main_module_is_served(self, e2e_pipeline):
        resp = urllib.request.urlopen(e2e_pipeline["url"] + "main.js", timeout=5)
        assert resp.status == 200

    def test_data_json_is_served(self, e2e_pipeline):
        resp = urllib.request.urlopen(e2e_pipeline["url"] + "data.json", timeout=5)
        assert resp.status == 200

    def test_data_json_has_correct_run_name(self, e2e_pipeline):
        body = urllib.request.urlopen(e2e_pipeline["url"] + "data.json", timeout=5).read()
        data = json.loads(body.decode())
        assert data["meta"]["name"] == e2e_pipeline["run_name"]

    def test_data_json_file_count_is_correct(self, e2e_pipeline):
        body = urllib.request.urlopen(e2e_pipeline["url"] + "data.json", timeout=5).read()
        data = json.loads(body.decode())
        assert data["meta"]["total_files"] == 5

    def test_module_is_served(self, e2e_pipeline):
        resp = urllib.request.urlopen(e2e_pipeline["url"] + "core/theme.js", timeout=5)
        assert resp.status == 200
        assert "javascript" in resp.headers.get("Content-Type", "")

    def test_unknown_path_returns_404(self, e2e_pipeline):
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(e2e_pipeline["url"] + "nonexistent.html", timeout=5)
        assert exc.value.code == 404

    def test_parent_directory_traversal_is_blocked(self, e2e_pipeline):
        # Files outside the report dir should not be accessible
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(e2e_pipeline["url"] + "../splora.py", timeout=5)
        assert exc.value.code in (400, 404)
