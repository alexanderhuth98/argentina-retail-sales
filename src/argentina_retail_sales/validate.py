from collections.abc import Callable

import pandas as pd

from . import config
from .transform import load_source


def _close(left: pd.Series, right: pd.Series) -> pd.Series:
    difference = (left - right).abs()
    allowed = config.RECONCILIATION_ABS_TOLERANCE + (
        config.RECONCILIATION_REL_TOLERANCE * right.abs()
    )
    return difference <= allowed


def _source_checks(source_name: str, frame: pd.DataFrame) -> list[dict[str, object]]:
    total_categories = (
        "ventas_totales_grupo_articulos"
        if source_name == "supermarkets"
        else "ventas_totales_grupos_articulos"
    )
    showroom = "salon_ventas" if source_name == "supermarkets" else "salon_de_ventas"
    food_components = [
        "bebidas",
        "almacen",
        "panaderia",
        "lacteos",
        "carnes",
        "verduleria_fruteria",
    ]
    if source_name == "supermarkets":
        food_components.append("alimentos_preparados_rotiseria")

    checks: list[tuple[str, Callable[[], bool], str]] = [
        (
            "headline_scale_reconciles",
            lambda: _close(
                frame["ventas_precios_corrientes"] * 1000,
                frame["ventas_totales_canal_venta"],
            ).all(),
            "Current-price headline millions reconcile to detailed thousands.",
        ),
        (
            "payment_components_reconcile",
            lambda: _close(
                frame[["efectivo", "tarjetas_debito", "tarjetas_credito", "otros_medios"]].sum(
                    axis=1
                ),
                frame["ventas_totales_medio_pago"],
            ).all(),
            "Payment components reconcile to their total.",
        ),
        (
            "food_components_reconcile",
            lambda: _close(
                frame[food_components].sum(axis=1),
                frame["subtotal_ventas_alimentos_bebidas"]
                if source_name == "supermarkets"
                else frame["subtotal_alimentos_bebidas"],
            ).all(),
            "Food components reconcile to their subtotal.",
        ),
        (
            "nominal_totals_agree",
            lambda: _close(
                frame["ventas_totales_canal_venta"], frame["ventas_totales_medio_pago"]
            ).all()
            and _close(frame["ventas_totales_canal_venta"], frame[total_categories]).all(),
            "Channel, payment and category totals agree.",
        ),
    ]

    observed_channel = frame[[showroom, "canales_on_line"]].notna().all(axis=1)
    checks.append(
        (
            "observed_channel_components_reconcile",
            lambda: _close(
                frame.loc[observed_channel, showroom]
                + frame.loc[observed_channel, "canales_on_line"],
                frame.loc[observed_channel, "ventas_totales_canal_venta"],
            ).all(),
            "Observed channel components reconcile; unavailable months are excluded.",
        )
    )

    if source_name == "wholesale":
        checks.append(
            (
                "wholesale_channel_gap_preserved",
                lambda: frame.loc[
                    frame["indice_tiempo"] >= "2022-09-01", [showroom, "canales_on_line"]
                ]
                .isna()
                .all()
                .all(),
                "Wholesale channel detail remains unavailable from September 2022.",
            )
        )

    results = []
    for check_name, calculation, detail in checks:
        passed = bool(calculation())
        results.append(
            {
                "source": source_name,
                "check": check_name,
                "severity": "HIGH",
                "status": "PASS" if passed else "FAIL",
                "detail": detail,
            }
        )
    return results


def validate_all(write_output: bool = True) -> pd.DataFrame:
    config.ensure_directories()
    results = []
    for source_name, source in config.SOURCES.items():
        frame = load_source(source_name, config.RAW_DIR / source["filename"])
        results.extend(_source_checks(source_name, frame))

    report = pd.DataFrame(results)
    if write_output:
        report.to_csv(config.PORTFOLIO_DATA_DIR / "quality_checks.csv", index=False)
    failed = report.loc[report["status"] == "FAIL"]
    if not failed.empty:
        raise ValueError(f"Quality validation failed: {failed['check'].tolist()}")
    return report
