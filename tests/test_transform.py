from pathlib import Path

import pandas as pd
import pytest

from argentina_retail_sales.transform import DataContractError, build_outputs, load_source


def test_load_source_enforces_monthly_contract(
    raw_sources: Path, source_frames: dict[str, pd.DataFrame]
) -> None:
    loaded = load_source("supermarkets", raw_sources / "supermarkets.csv")
    assert len(loaded) == 14
    assert pd.api.types.is_datetime64_any_dtype(loaded["indice_tiempo"])

    broken = source_frames["supermarkets"].drop(index=1)
    broken.to_csv(raw_sources / "supermarkets.csv", index=False)
    with pytest.raises(DataContractError, match="Missing months"):
        load_source("supermarkets", raw_sources / "supermarkets.csv")


def test_load_source_rejects_schema_change(
    raw_sources: Path, source_frames: dict[str, pd.DataFrame]
) -> None:
    broken = source_frames["wholesale"].rename(columns={"efectivo": "cash"})
    broken.to_csv(raw_sources / "wholesale.csv", index=False)
    with pytest.raises(DataContractError, match="Unexpected columns"):
        load_source("wholesale", raw_sources / "wholesale.csv")


def test_build_outputs_creates_tidy_marts(source_frames: dict[str, pd.DataFrame]) -> None:
    frames = {
        name: frame.assign(indice_tiempo=pd.to_datetime(frame["indice_tiempo"]))
        for name, frame in source_frames.items()
    }
    outputs = build_outputs(frames)

    assert set(outputs) == {"monthly_summary", "payment_mix", "category_mix", "channel_mix"}
    assert len(outputs["monthly_summary"]) == 28
    assert outputs["payment_mix"]["share_pct"].between(0, 100).all()
    assert (
        outputs["category_mix"]
        .loc[outputs["category_mix"]["category"] == "prepared_food", "retail_format"]
        .eq("supermarkets")
        .all()
    )
    assert outputs["monthly_summary"]["real_sales_yoy_pct"].notna().sum() == 4


def test_wholesale_missing_channel_is_not_imputed(source_frames: dict[str, pd.DataFrame]) -> None:
    wholesale = source_frames["wholesale"].assign(
        indice_tiempo=pd.to_datetime(source_frames["wholesale"]["indice_tiempo"])
    )
    wholesale.loc[wholesale.index[-1], ["salon_de_ventas", "canales_on_line"]] = pd.NA
    outputs = build_outputs({"wholesale": wholesale})
    latest = outputs["channel_mix"].loc[outputs["channel_mix"]["month"] == "2022-02-01"]
    assert latest["sales_thousand_ars"].isna().all()
    assert not latest["is_observed"].any()
