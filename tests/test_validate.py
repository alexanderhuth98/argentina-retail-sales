from pathlib import Path

import pandas as pd
import pytest

from argentina_retail_sales import config, validate


def _patch_paths(monkeypatch: pytest.MonkeyPatch, raw: Path, output: Path) -> None:
    monkeypatch.setattr(config, "RAW_DIR", raw)
    monkeypatch.setattr(config, "PORTFOLIO_DATA_DIR", output)
    monkeypatch.setattr(config, "OUTPUT_DIR", output)
    monkeypatch.setattr(config, "MANIFEST_DIR", output)


def test_validation_passes_reconciled_sources(
    monkeypatch: pytest.MonkeyPatch, raw_sources: Path, tmp_path: Path
) -> None:
    _patch_paths(monkeypatch, raw_sources, tmp_path)
    report = validate.validate_all()
    assert report["status"].eq("PASS").all()
    assert (tmp_path / "quality_checks.csv").exists()


def test_validation_fails_broken_payment_total(
    monkeypatch: pytest.MonkeyPatch, raw_sources: Path, tmp_path: Path
) -> None:
    wholesale_path = raw_sources / "wholesale.csv"
    wholesale = pd.read_csv(wholesale_path)
    wholesale.loc[0, "efectivo"] += 100
    wholesale.to_csv(wholesale_path, index=False)
    _patch_paths(monkeypatch, raw_sources, tmp_path)

    with pytest.raises(ValueError, match="payment_components_reconcile"):
        validate.validate_all()
