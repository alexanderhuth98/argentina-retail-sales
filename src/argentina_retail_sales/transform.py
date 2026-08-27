from pathlib import Path

import pandas as pd

from . import config


class DataContractError(ValueError):
    """Raised when an official source no longer matches its declared contract."""


def load_source(source_name: str, path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    expected = config.EXPECTED_COLUMNS[source_name]
    if frame.columns.tolist() != expected:
        raise DataContractError(f"Unexpected columns for {source_name}: {frame.columns.tolist()}")

    frame["indice_tiempo"] = pd.to_datetime(frame["indice_tiempo"], errors="raise")
    if frame["indice_tiempo"].duplicated().any():
        raise DataContractError(f"Duplicate months in {source_name}")
    if not frame["indice_tiempo"].is_monotonic_increasing:
        raise DataContractError(f"Months are not ordered in {source_name}")
    if not frame["indice_tiempo"].dt.is_month_start.all():
        raise DataContractError(f"Dates must be month starts in {source_name}")

    expected_months = pd.date_range(
        frame["indice_tiempo"].min(), frame["indice_tiempo"].max(), freq="MS"
    )
    if not frame["indice_tiempo"].reset_index(drop=True).equals(pd.Series(expected_months)):
        raise DataContractError(f"Missing months in {source_name}")

    numeric = frame.drop(columns="indice_tiempo")
    if (numeric < 0).any().any():
        raise DataContractError(f"Negative values in {source_name}")
    return frame


def _monthly_summary(frame: pd.DataFrame, retail_format: str) -> pd.DataFrame:
    summary = frame[
        [
            "indice_tiempo",
            "ventas_precios_corrientes",
            "ventas_precios_constantes",
            "ventas_precios_constantes_original",
            "ventas_precios_constantes_desestacionalizada",
            "ventas_precios_constantes_tendencia_ciclo",
        ]
    ].copy()
    summary.insert(1, "retail_format", retail_format)
    summary = summary.rename(
        columns={
            "indice_tiempo": "month",
            "ventas_precios_corrientes": "nominal_sales_million_ars",
            "ventas_precios_constantes": "constant_sales_million_ars",
            "ventas_precios_constantes_original": "real_sales_index_original",
            "ventas_precios_constantes_desestacionalizada": "real_sales_index_sa",
            "ventas_precios_constantes_tendencia_ciclo": "real_sales_index_trend",
        }
    )
    summary["nominal_sales_yoy_pct"] = (
        summary["nominal_sales_million_ars"].pct_change(12, fill_method=None) * 100
    )
    summary["real_sales_yoy_pct"] = (
        summary["real_sales_index_original"].pct_change(12, fill_method=None) * 100
    )
    summary["real_sales_sa_mom_pct"] = (
        summary["real_sales_index_sa"].pct_change(fill_method=None) * 100
    )
    summary["is_partial_year"] = summary["month"].dt.year.eq(summary["month"].max().year)
    return summary


def _long_mix(
    frame: pd.DataFrame,
    retail_format: str,
    mapping: dict[str, str],
    dimension_name: str,
) -> pd.DataFrame:
    available = [column for column in mapping if column in frame.columns]
    result = frame[["indice_tiempo", *available]].melt(
        id_vars="indice_tiempo",
        value_vars=available,
        var_name="source_metric",
        value_name="sales_thousand_ars",
    )
    result.insert(1, "retail_format", retail_format)
    result[dimension_name] = result["source_metric"].map(mapping)
    result["is_observed"] = result["sales_thousand_ars"].notna()
    totals = frame.set_index("indice_tiempo")["ventas_totales_medio_pago"]
    result["share_pct"] = result["sales_thousand_ars"] / result["indice_tiempo"].map(totals) * 100
    return result.rename(columns={"indice_tiempo": "month"})[
        [
            "month",
            "retail_format",
            dimension_name,
            "sales_thousand_ars",
            "share_pct",
            "is_observed",
        ]
    ]


def _channel_mix(frame: pd.DataFrame, retail_format: str) -> pd.DataFrame:
    showroom = "salon_ventas" if retail_format == "supermarkets" else "salon_de_ventas"
    mapping = {showroom: "showroom", "canales_on_line": "online"}
    result = frame[["indice_tiempo", showroom, "canales_on_line"]].melt(
        id_vars="indice_tiempo",
        var_name="source_metric",
        value_name="sales_thousand_ars",
    )
    result.insert(1, "retail_format", retail_format)
    result["channel"] = result["source_metric"].map(mapping)
    result["is_observed"] = result["sales_thousand_ars"].notna()
    totals = frame.set_index("indice_tiempo")["ventas_totales_canal_venta"]
    result["share_pct"] = result["sales_thousand_ars"] / result["indice_tiempo"].map(totals) * 100
    return result.rename(columns={"indice_tiempo": "month"})[
        [
            "month",
            "retail_format",
            "channel",
            "sales_thousand_ars",
            "share_pct",
            "is_observed",
        ]
    ]


def build_outputs(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    summaries = []
    payments = []
    categories = []
    channels = []

    for retail_format, frame in frames.items():
        summaries.append(_monthly_summary(frame, retail_format))
        payments.append(_long_mix(frame, retail_format, config.PAYMENT_COLUMNS, "payment_method"))
        category_mix = _long_mix(frame, retail_format, config.CATEGORY_COLUMNS, "category")
        category_mix["comparable_across_formats"] = category_mix["category"].ne("prepared_food")
        categories.append(category_mix)
        channels.append(_channel_mix(frame, retail_format))

    return {
        "monthly_summary": pd.concat(summaries, ignore_index=True),
        "payment_mix": pd.concat(payments, ignore_index=True),
        "category_mix": pd.concat(categories, ignore_index=True),
        "channel_mix": pd.concat(channels, ignore_index=True),
    }


def build_all() -> dict[str, pd.DataFrame]:
    config.ensure_directories()
    frames = {
        source_name: load_source(source_name, config.RAW_DIR / source["filename"])
        for source_name, source in config.SOURCES.items()
    }
    outputs = build_outputs(frames)
    for output_name, frame in outputs.items():
        frame.to_csv(config.PORTFOLIO_DATA_DIR / f"{output_name}.csv", index=False)
    return outputs
