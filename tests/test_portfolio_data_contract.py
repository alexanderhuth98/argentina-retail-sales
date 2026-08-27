from pathlib import Path

import pandas as pd
import pytest

DATA = Path(__file__).parents[1] / "portfolio_data"


def test_published_portfolio_reconciles_and_passes_high_gate():
    monthly = pd.read_csv(DATA / "monthly_summary.csv", parse_dates=["month"])
    payments = pd.read_csv(DATA / "payment_mix.csv")
    categories = pd.read_csv(DATA / "category_mix.csv")
    channels = pd.read_csv(DATA / "channel_mix.csv", parse_dates=["month"])
    quality = pd.read_csv(DATA / "quality_checks.csv")

    assert len(monthly) == 226
    assert len(payments) == 904
    assert len(categories) == 2_373
    assert len(channels) == 452
    assert len(quality) == 11
    assert monthly.groupby(["month", "retail_format"]).size().eq(1).all()
    assert (
        payments.groupby(["month", "retail_format"])["share_pct"]
        .sum()
        .sub(100)
        .abs()
        .le(0.01)
        .all()
    )
    assert (
        categories.groupby(["month", "retail_format"])["share_pct"]
        .sum()
        .sub(100)
        .abs()
        .le(0.01)
        .all()
    )
    observed_channels = channels.loc[channels["is_observed"]]
    assert (
        observed_channels.groupby(["month", "retail_format"])["share_pct"]
        .sum()
        .sub(100)
        .abs()
        .le(0.01)
        .all()
    )
    assert quality.loc[(quality["severity"] == "HIGH") & (quality["status"] != "PASS")].empty


def test_documented_latest_findings_match_published_snapshot():
    monthly = pd.read_csv(DATA / "monthly_summary.csv", parse_dates=["month"])
    payments = pd.read_csv(DATA / "payment_mix.csv", parse_dates=["month"])
    categories = pd.read_csv(DATA / "category_mix.csv", parse_dates=["month"])
    channels = pd.read_csv(DATA / "channel_mix.csv", parse_dates=["month"])

    latest_month = monthly["month"].max()
    assert latest_month == pd.Timestamp("2026-05-01")
    latest = monthly.loc[monthly["month"] == latest_month].set_index("retail_format")
    assert latest.loc["supermarkets", "real_sales_index_original"] == pytest.approx(
        80.5167, abs=0.0001
    )
    assert latest.loc["supermarkets", "real_sales_yoy_pct"] == pytest.approx(-0.6757, abs=0.0001)
    assert latest.loc["wholesale", "real_sales_index_original"] == pytest.approx(
        80.5850, abs=0.0001
    )
    assert latest.loc["wholesale", "real_sales_yoy_pct"] == pytest.approx(-2.3151, abs=0.0001)

    latest_payments = payments.loc[payments["month"] == latest_month].set_index(
        ["retail_format", "payment_method"]
    )
    assert latest_payments.loc[("supermarkets", "credit_card"), "share_pct"] == pytest.approx(
        44.9739, abs=0.0001
    )
    assert latest_payments.loc[("wholesale", "other"), "share_pct"] == pytest.approx(
        32.3178, abs=0.0001
    )

    latest_categories = categories.loc[categories["month"] == latest_month]
    leaders = latest_categories.loc[
        latest_categories.groupby("retail_format")["share_pct"].idxmax()
    ]
    assert set(leaders["category"]) == {"grocery"}

    observed_online = channels.loc[(channels["channel"] == "online") & channels["is_observed"]]
    wholesale_cutoff = observed_online.loc[
        observed_online["retail_format"] == "wholesale", "month"
    ].max()
    assert wholesale_cutoff == pd.Timestamp("2022-08-01")
