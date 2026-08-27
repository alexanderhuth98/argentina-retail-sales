from pathlib import Path

import pandas as pd
import pytest

from argentina_retail_sales import config


def _frame(source_name: str) -> pd.DataFrame:
    rows = []
    for month_number, month in enumerate(pd.date_range("2021-01-01", periods=14, freq="MS"), 1):
        total = 100_000.0 + month_number * 1_000
        row = {column: 1.0 for column in config.EXPECTED_COLUMNS[source_name]}
        row["indice_tiempo"] = month.strftime("%Y-%m-%d")
        row["ventas_precios_corrientes"] = total / 1000
        row["ventas_precios_constantes"] = 90.0 + month_number
        row["ventas_precios_constantes_original"] = 90.0 + month_number
        row["ventas_precios_constantes_desestacionalizada"] = 90.0 + month_number
        row["ventas_precios_constantes_tendencia_ciclo"] = 90.0 + month_number
        row["ventas_totales_canal_venta"] = total
        row["ventas_totales_medio_pago"] = total
        total_categories = (
            "ventas_totales_grupo_articulos"
            if source_name == "supermarkets"
            else "ventas_totales_grupos_articulos"
        )
        row[total_categories] = total
        showroom = "salon_ventas" if source_name == "supermarkets" else "salon_de_ventas"
        row[showroom] = total * 0.9
        row["canales_on_line"] = total * 0.1
        for column, share in zip(config.PAYMENT_COLUMNS, (0.2, 0.2, 0.5, 0.1), strict=True):
            row[column] = total * share

        food_columns = [
            "bebidas",
            "almacen",
            "panaderia",
            "lacteos",
            "carnes",
            "verduleria_fruteria",
        ]
        if source_name == "supermarkets":
            food_columns.append("alimentos_preparados_rotiseria")
        food_total = total * 0.7
        for column in food_columns:
            row[column] = food_total / len(food_columns)
        food_subtotal = (
            "subtotal_ventas_alimentos_bebidas"
            if source_name == "supermarkets"
            else "subtotal_alimentos_bebidas"
        )
        row[food_subtotal] = food_total
        for column in (
            "articulos_limpieza_perfumeria",
            "indumentaria_calzado_textiles_hogar",
            "electronicos_articulos_hogar",
            "otros",
        ):
            row[column] = total * 0.075
        rows.append(row)
    return pd.DataFrame(rows, columns=config.EXPECTED_COLUMNS[source_name])


@pytest.fixture
def source_frames() -> dict[str, pd.DataFrame]:
    return {name: _frame(name) for name in config.SOURCES}


@pytest.fixture
def raw_sources(tmp_path: Path, source_frames: dict[str, pd.DataFrame]) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    for source_name, frame in source_frames.items():
        frame.to_csv(raw / config.SOURCES[source_name]["filename"], index=False)
    return raw
