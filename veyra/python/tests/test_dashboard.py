from pathlib import Path

from veyra.view import overview, page_bytes


def test_dashboard_page_is_packaged_and_names_the_screens():
    html = page_bytes().decode("utf-8")
    for label in ("Overview", "Runs", "Decisions", "Evaluation", "Install"):
        assert label in html
    assert "not a Kev result" not in html


def test_overview_reports_unmeasured_public_benchmarks(tmp_path: Path):
    data = overview(tmp_path)
    assert data["version"]
    assert data["runs"] == []
    assert any(t["id"] == "harbor-public" and t["status"] == "not_run" for t in data["targets"])
