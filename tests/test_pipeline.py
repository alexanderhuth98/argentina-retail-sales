import sys

import pytest

from argentina_retail_sales import pipeline


def test_all_stage_runs_every_step(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(sys, "argv", ["argentina-retail-sales", "all", "--force"])
    monkeypatch.setattr(pipeline, "download_all", lambda force: calls.append(("download", force)))
    monkeypatch.setattr(pipeline, "build_all", lambda: calls.append(("build", None)))
    monkeypatch.setattr(pipeline, "validate_all", lambda: calls.append(("validate", None)))

    pipeline.main()

    assert calls == [("download", True), ("build", None), ("validate", None)]
