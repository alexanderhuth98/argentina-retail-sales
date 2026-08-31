from pathlib import Path

import pandas as pd
import pytest

from argentina_retail_sales.dashboard import (
    DashboardContractError,
    build_dashboard_payload,
    export_dashboard,
    load_dashboard_data,
    quality_gate,
    render_dashboard,
)


@pytest.fixture
def dashboard_marts(tmp_path: Path) -> Path:
    months = pd.date_range("2021-09-01", periods=13, freq="MS")
    monthly = []
    payments = []
    categories = []
    channels = []
    for retail_format in ("supermarkets", "wholesale"):
        for index, month in enumerate(months):
            monthly.append(
                {
                    "month": month,
                    "retail_format": retail_format,
                    "nominal_sales_million_ars": 100 + index * 10,
                    "constant_sales_million_ars": 90 + index,
                    "real_sales_index_original": 100 + index,
                    "real_sales_index_sa": 101 + index,
                    "real_sales_index_trend": 100.5 + index,
                    "nominal_sales_yoy_pct": None,
                    "real_sales_yoy_pct": 12 if index == 12 else None,
                    "real_sales_sa_mom_pct": 1 if index else None,
                    "is_partial_year": month.year == 2022,
                }
            )
            for method, share in {
                "cash": 20,
                "debit_card": 25,
                "credit_card": 45,
                "other": 10,
            }.items():
                payments.append(
                    {
                        "month": month,
                        "retail_format": retail_format,
                        "payment_method": method,
                        "sales_thousand_ars": share * 1000,
                        "share_pct": share,
                        "is_observed": True,
                    }
                )
            for category, share in {"grocery": 60, "beverages": 40}.items():
                categories.append(
                    {
                        "month": month,
                        "retail_format": retail_format,
                        "category": category,
                        "sales_thousand_ars": share * (1000 + index * 10),
                        "share_pct": share,
                        "is_observed": True,
                    }
                )
            channel_observed = retail_format == "supermarkets" or month <= pd.Timestamp(
                "2022-08-01"
            )
            for channel, share in {"showroom": 95, "online": 5}.items():
                channels.append(
                    {
                        "month": month,
                        "retail_format": retail_format,
                        "channel": channel,
                        "sales_thousand_ars": share * 1000 if channel_observed else None,
                        "share_pct": share if channel_observed else None,
                        "is_observed": channel_observed,
                    }
                )

    pd.DataFrame(monthly).to_csv(tmp_path / "monthly_summary.csv", index=False)
    pd.DataFrame(payments).to_csv(tmp_path / "payment_mix.csv", index=False)
    pd.DataFrame(categories).to_csv(tmp_path / "category_mix.csv", index=False)
    pd.DataFrame(channels).to_csv(tmp_path / "channel_mix.csv", index=False)
    pd.DataFrame(
        [
            {
                "source": "supermarkets",
                "check": "safe_detail",
                "severity": "HIGH",
                "status": "PASS",
                "detail": "Contenido validado",
            }
        ]
    ).to_csv(tmp_path / "quality_checks.csv", index=False)
    return tmp_path


def test_dashboard_calculations_and_missing_channel_contract(dashboard_marts: Path) -> None:
    payment_path = dashboard_marts / "payment_mix.csv"
    payments = pd.read_csv(payment_path)
    payments[payments.columns[::-1]].to_csv(payment_path, index=False)

    frames = load_dashboard_data(dashboard_marts)
    payment_totals = frames["payment_mix"].groupby(["month", "retail_format"])["share_pct"].sum()
    category_totals = frames["category_mix"].groupby(["month", "retail_format"])["share_pct"].sum()
    assert payment_totals.eq(100).all()
    assert category_totals.eq(100).all()
    assert (
        frames["payment_mix"]
        .loc[frames["payment_mix"]["month"] == "2022-09-01", "share_yoy_pp"]
        .eq(0)
        .all()
    )
    assert (
        frames["category_mix"]
        .loc[frames["category_mix"]["month"] == "2022-09-01", "nominal_sales_yoy_pct"]
        .notna()
        .all()
    )

    observed_wholesale = frames["channel_mix"].loc[
        (frames["channel_mix"]["retail_format"] == "wholesale")
        & frames["channel_mix"]["is_observed"]
    ]
    assert observed_wholesale["month"].max() == pd.Timestamp("2022-08-01")
    unavailable = frames["channel_mix"].loc[
        (frames["channel_mix"]["retail_format"] == "wholesale")
        & (frames["channel_mix"]["month"] > "2022-08-01")
    ]
    assert unavailable["share_pct"].isna().all()


def test_quality_gate_requires_high_checks_and_blocks_failures() -> None:
    assert quality_gate([]) == "BLOCKED"
    assert quality_gate([{"severity": "LOW", "status": "PASS"}]) == "BLOCKED"
    assert quality_gate([{"severity": "HIGH", "status": "PASS"}]) == "PASS"
    assert quality_gate([{"severity": "HIGH", "status": "FAIL"}]) == "BLOCKED"


def test_rendered_variants_include_metadata_and_safe_content(dashboard_marts: Path) -> None:
    quality_path = dashboard_marts / "quality_checks.csv"
    quality = pd.read_csv(quality_path)
    quality.loc[0, "detail"] = "</script><script>alert('x')</script>"
    quality.to_csv(quality_path, index=False)
    payload = build_dashboard_payload(dashboard_marts)
    first_month = payload["monthly_summary"][0]

    desktop = render_dashboard(payload)
    mobile = render_dashboard(payload, mobile=True)

    for html in (desktop, mobile):
        assert '<html lang="es"' in html
        assert 'name="viewport"' in html
        assert "plotly-2.35.2.min.js" in html
        assert "DOMContentLoaded" in html
        assert "node.replaceChildren();window.Plotly.react" in html
        assert "No observado" in html
        assert "CC BY 4.0" in html
        assert "NaN" not in html
        assert "</script><script>alert('x')</script>" not in html
        assert "\\u003c/script\\u003e" in html
    assert 'class="desktop"' in desktop
    assert 'data-variant="escritorio"' in desktop
    assert 'class="mobile"' in mobile
    assert 'data-variant="móvil"' in mobile
    assert payload["metadata"]["gate"] == "PASS"
    assert first_month["real_sales_yoy_pct"] is None


def test_export_writes_both_pages_and_pages_support_files(
    dashboard_marts: Path, tmp_path: Path
) -> None:
    site = tmp_path / "site"
    desktop, mobile = export_dashboard(dashboard_marts, site)
    assert desktop == site / "index.html"
    assert mobile == site / "mobile.html"
    assert desktop.exists() and mobile.exists()
    assert (site / ".nojekyll").exists()
    assert "No edite" in (site / "README.md").read_text(encoding="utf-8")


def test_export_blocks_site_when_high_gate_fails(dashboard_marts: Path, tmp_path: Path) -> None:
    checks = pd.read_csv(dashboard_marts / "quality_checks.csv")
    checks.loc[0, "status"] = "FAIL"
    checks.to_csv(dashboard_marts / "quality_checks.csv", index=False)

    with pytest.raises(DashboardContractError, match="Gate HIGH bloqueado"):
        export_dashboard(dashboard_marts, tmp_path / "site")


def test_real_portfolio_data_exports_without_contract_drift(tmp_path: Path) -> None:
    project_root = Path(__file__).parents[1]
    desktop, mobile = export_dashboard(project_root / "portfolio_data", tmp_path / "site")

    assert desktop.stat().st_size > 300_000
    assert mobile.stat().st_size > 300_000
    assert "2022-08-01" in desktop.read_text(encoding="utf-8")


def test_versioned_site_matches_real_renderer() -> None:
    project_root = Path(__file__).parents[1]
    payload = build_dashboard_payload(
        project_root / "portfolio_data", project_root / "manifests" / "raw_sources.jsonl"
    )

    assert (project_root / "site" / "index.html").read_text(encoding="utf-8") == render_dashboard(
        payload
    )
    assert (project_root / "site" / "mobile.html").read_text(encoding="utf-8") == render_dashboard(
        payload, mobile=True
    )
