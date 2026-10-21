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


@pytest.mark.parametrize(
    ("source_name", "check_name"),
    [
        (source_name, check_name)
        for source_name in ("supermarkets", "wholesale")
        for check_name in (
            "headline_scale_reconciles",
            "payment_components_reconcile",
            "food_components_reconcile",
            "nominal_totals_agree",
            "observed_channel_components_reconcile",
        )
    ]
    + [("wholesale", "wholesale_channel_gap_preserved")],
)
def test_each_high_check_detects_representative_mutation(
    source_frames: dict[str, pd.DataFrame], source_name: str, check_name: str
) -> None:
    frame = source_frames[source_name].copy()
    showroom = "salon_ventas" if source_name == "supermarkets" else "salon_de_ventas"
    if check_name == "headline_scale_reconciles":
        frame.loc[0, "ventas_precios_corrientes"] += 1
    elif check_name == "payment_components_reconcile":
        frame.loc[0, "efectivo"] += 100
    elif check_name == "food_components_reconcile":
        frame.loc[0, "bebidas"] += 100
    elif check_name == "nominal_totals_agree":
        total_categories = (
            "ventas_totales_grupo_articulos"
            if source_name == "supermarkets"
            else "ventas_totales_grupos_articulos"
        )
        frame.loc[0, total_categories] += 100
    elif check_name == "observed_channel_components_reconcile":
        frame.loc[0, showroom] += 100
    else:
        frame.loc[frame.index[-1], "indice_tiempo"] = "2022-09-01"

    report = pd.DataFrame(validate._source_checks(source_name, frame))

    status = report.loc[report["check"] == check_name, "status"].item()
    assert status == "FAIL"
