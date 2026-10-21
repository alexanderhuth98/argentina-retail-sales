import hashlib
from pathlib import Path

import pandas as pd
import pytest

from argentina_retail_sales.dashboard import (
    ASSET_HASHES,
    ASSET_SOURCE_DIR,
    DashboardContractError,
    add_group_yoy,
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


def test_group_yoy_uses_exact_calendar_month_with_shuffled_missing_rows() -> None:
    months = list(pd.date_range("2022-01-01", "2022-12-01", freq="MS"))
    months.remove(pd.Timestamp("2022-06-01"))
    months.extend([pd.Timestamp("2023-01-01"), pd.Timestamp("2023-06-01")])
    frame = pd.DataFrame(
        {
            "month": months,
            "retail_format": "supermarkets",
            "category": "grocery",
            "value": [100 if month == pd.Timestamp("2022-01-01") else 120 for month in months],
        }
    ).sample(frac=1, random_state=7)

    result = add_group_yoy(frame, "category", "value", "yoy", percentage=True)

    january = result.loc[result["month"] == "2023-01-01", "yoy"].item()
    missing_prior = result.loc[result["month"] == "2023-06-01", "yoy"].item()
    assert january == pytest.approx(20)
    assert pd.isna(missing_prior)
    assert result.index.equals(frame.index)


def test_group_yoy_returns_missing_when_exact_prior_value_is_zero() -> None:
    frame = pd.DataFrame(
        {
            "month": pd.to_datetime(["2022-03-01", "2023-03-01"]),
            "retail_format": ["wholesale", "wholesale"],
            "category": ["beverages", "beverages"],
            "value": [0, 25],
        }
    )

    result = add_group_yoy(frame, "category", "value", "yoy", percentage=True)

    assert pd.isna(result.loc[1, "yoy"])


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_file", "Falta el mart curado"),
        ("missing_column", "Columnas faltantes"),
        ("bad_month", "Mes inválido"),
        ("bad_format", "Formato inesperado"),
        ("duplicate_key", "Claves duplicadas"),
        ("infinite_value", "Valores infinitos"),
    ],
)
def test_dashboard_mart_failures_are_explicit(
    dashboard_marts: Path, mutation: str, message: str
) -> None:
    path = dashboard_marts / "monthly_summary.csv"
    frame = pd.read_csv(path)
    if mutation == "missing_file":
        path.unlink()
    elif mutation == "missing_column":
        frame.drop(columns="real_sales_index_sa").to_csv(path, index=False)
    elif mutation == "bad_month":
        frame.loc[0, "month"] = "not-a-month"
        frame.to_csv(path, index=False)
    elif mutation == "bad_format":
        frame.loc[0, "retail_format"] = "unknown"
        frame.to_csv(path, index=False)
    elif mutation == "duplicate_key":
        pd.concat([frame, frame.iloc[[0]]], ignore_index=True).to_csv(path, index=False)
    else:
        frame["real_sales_index_sa"] = frame["real_sales_index_sa"].astype(float)
        frame.loc[0, "real_sales_index_sa"] = float("inf")
        frame.to_csv(path, index=False)

    with pytest.raises(DashboardContractError, match=message):
        load_dashboard_data(dashboard_marts)


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
        assert '<html lang="es-AR"' in html
        assert 'name="viewport"' in html
        assert '<link rel="icon" href="https://alexanderhuth98.github.io/favicon.ico"' in html
        assert '<meta name="referrer" content="strict-origin-when-cross-origin">' in html
        assert 'data-goatcounter="https://alexanderhuth98.goatcounter.com/count"' in html
        assert 'src="assets/plotly-basic-2.35.2.min.js"' in html
        assert "cdn.plot.ly" not in html
        assert "https://cdn" not in html
        assert "DOMContentLoaded" in html
        assert "Promise.resolve(result).then" in html
        assert ".catch(error=>plotFailure" in html
        assert "fallback.hidden=true" in html
        assert "Plotly no está disponible" in html
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


@pytest.mark.parametrize("mobile", [False, True])
def test_rendered_variants_publish_social_metadata_and_primary_canonical(
    dashboard_marts: Path, mobile: bool
) -> None:
    html = render_dashboard(build_dashboard_payload(dashboard_marts), mobile=mobile)
    primary_url = "https://alexanderhuth98.github.io/argentina-retail-sales/"
    image_url = "https://alexanderhuth98.github.io/assets/projects/retail-analysis.png"
    title = "Pulso del retail argentino"
    description = (
        "Tablero de ventas reales, pagos, categorías, canales y calidad del retail argentino."
    )

    expected_tags = (
        f'<meta name="description" content="{description}">',
        '<meta name="author" content="Alexander Huth">',
        '<meta name="theme-color" content="#0b1111">',
        f'<link rel="canonical" href="{primary_url}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:locale" content="es_AR">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{description}">',
        f'<meta property="og:url" content="{primary_url}">',
        f'<meta property="og:image" content="{image_url}">',
        '<meta property="og:image:alt" content="Dashboard Pulso del retail argentino">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{title}">',
        f'<meta name="twitter:description" content="{description}">',
        f'<meta name="twitter:image" content="{image_url}">',
        '<meta name="twitter:image:alt" content="Dashboard Pulso del retail argentino">',
    )
    for tag in expected_tags:
        assert tag in html
    assert html.count('rel="canonical"') == 1
    assert 'rel="canonical" href="mobile.html"' not in html


def test_dashboard_identity_and_recoverable_zoom_contract(dashboard_marts: Path) -> None:
    html = render_dashboard(build_dashboard_payload(dashboard_marts))

    for token in (
        "--bg:#0b1111",
        "--bg-deep:#080d0d",
        "--surface:#171d1e",
        "--surface-raised:#1b2223",
        "--surface-soft:#111819",
        "--text:#edf1ef",
        "--muted:#a5aeaa",
        "--dim:#89938f",
        "--mint:#9ef6e5",
        "--mint-bright:#58e4d0",
        "--amber:#f3ce62",
        "--border:rgba(158,246,229,.11)",
        "--border-strong:rgba(158,246,229,.25)",
    ):
        assert token in html
    assert 'font-family:"Space Grotesk"' in html
    assert 'font-family:"IBM Plex Mono"' in html
    assert "box-shadow:none" in html
    assert "Volver a proyectos" in html
    assert "https://alexanderhuth98.github.io/#proyectos" in html
    assert "fixedrange:false" in html
    assert "displayModeBar:true" in html
    assert "displaylogo:false" in html
    assert "scrollZoom:false" in html
    assert "doubleClick:'reset+autosize'" in html
    assert "Restablecer vista" in html
    assert "Plotly.relayout" in html


def test_pinned_dashboard_assets_exist_and_match_hashes() -> None:
    for relative_path, expected_hash in ASSET_HASHES.items():
        asset = ASSET_SOURCE_DIR / relative_path
        assert asset.is_file(), relative_path
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == expected_hash


@pytest.mark.parametrize("failure", ["missing", "tampered"])
def test_export_rejects_missing_or_tampered_assets(
    dashboard_marts: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    from argentina_retail_sales import dashboard

    assets = tmp_path / "source-assets"
    assets.mkdir()
    asset = assets / "plotly.js"
    if failure == "tampered":
        asset.write_bytes(b"tampered")
    monkeypatch.setattr(dashboard, "ASSET_SOURCE_DIR", assets)
    monkeypatch.setattr(dashboard, "ASSET_HASHES", {"plotly.js": "0" * 64})

    message = "Falta el asset local" if failure == "missing" else "Integridad inválida"
    with pytest.raises(DashboardContractError, match=message):
        export_dashboard(dashboard_marts, tmp_path / "site")


def test_export_writes_both_pages_and_pages_support_files(
    dashboard_marts: Path, tmp_path: Path
) -> None:
    site = tmp_path / "site"
    desktop, mobile = export_dashboard(dashboard_marts, site)
    assert desktop == site / "index.html"
    assert mobile == site / "mobile.html"
    assert desktop.exists() and mobile.exists()
    assert (site / ".nojekyll").exists()
    assert (site / "404.html").exists()
    for relative_path in ASSET_HASHES:
        asset = site / "assets" / relative_path
        assert asset.is_file()
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == ASSET_HASHES[relative_path]
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
