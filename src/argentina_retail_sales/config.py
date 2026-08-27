import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("ARGENTINA_RETAIL_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PORTFOLIO_DATA_DIR = PROJECT_ROOT / "portfolio_data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
MANIFEST_DIR = PROJECT_ROOT / "manifests"

SCHEMA_VERSION = "1.0.0"
RECONCILIATION_ABS_TOLERANCE = 0.01  # Thousands of pesos.
RECONCILIATION_REL_TOLERANCE = 1e-9

SOURCES = {
    "supermarkets": {
        "filename": "supermarkets.csv",
        "url": "https://infra.datos.gob.ar/catalog/sspm/dataset/455/distribution/455.1/download/ventas-totales-supermercados-2.csv",
    },
    "wholesale": {
        "filename": "wholesale.csv",
        "url": "https://infra.datos.gob.ar/catalog/sspm/dataset/456/distribution/456.1/download/ventas-totales-autoservicios-mayoristas.csv",
    },
}

EXPECTED_COLUMNS = {
    "supermarkets": [
        "indice_tiempo",
        "ventas_precios_corrientes",
        "ventas_precios_constantes",
        "ventas_precios_constantes_original",
        "ventas_precios_constantes_desestacionalizada",
        "ventas_precios_constantes_tendencia_ciclo",
        "ventas_totales_canal_venta",
        "salon_ventas",
        "canales_on_line",
        "ventas_totales_medio_pago",
        "efectivo",
        "tarjetas_debito",
        "tarjetas_credito",
        "otros_medios",
        "ventas_totales_grupo_articulos",
        "subtotal_ventas_alimentos_bebidas",
        "bebidas",
        "almacen",
        "panaderia",
        "lacteos",
        "carnes",
        "verduleria_fruteria",
        "alimentos_preparados_rotiseria",
        "articulos_limpieza_perfumeria",
        "indumentaria_calzado_textiles_hogar",
        "electronicos_articulos_hogar",
        "otros",
    ],
    "wholesale": [
        "indice_tiempo",
        "ventas_precios_corrientes",
        "ventas_precios_constantes",
        "ventas_precios_constantes_original",
        "ventas_precios_constantes_desestacionalizada",
        "ventas_precios_constantes_tendencia_ciclo",
        "ventas_totales_canal_venta",
        "salon_de_ventas",
        "canales_on_line",
        "ventas_totales_medio_pago",
        "efectivo",
        "tarjetas_debito",
        "tarjetas_credito",
        "otros_medios",
        "ventas_totales_grupos_articulos",
        "subtotal_alimentos_bebidas",
        "bebidas",
        "almacen",
        "panaderia",
        "lacteos",
        "carnes",
        "verduleria_fruteria",
        "articulos_limpieza_perfumeria",
        "indumentaria_calzado_textiles_hogar",
        "electronicos_articulos_hogar",
        "otros",
    ],
}

PAYMENT_COLUMNS = {
    "efectivo": "cash",
    "tarjetas_debito": "debit_card",
    "tarjetas_credito": "credit_card",
    "otros_medios": "other",
}

CATEGORY_COLUMNS = {
    "bebidas": "beverages",
    "almacen": "grocery",
    "panaderia": "bakery",
    "lacteos": "dairy",
    "carnes": "meat",
    "verduleria_fruteria": "fruit_and_vegetables",
    "alimentos_preparados_rotiseria": "prepared_food",
    "articulos_limpieza_perfumeria": "cleaning_and_personal_care",
    "indumentaria_calzado_textiles_hogar": "clothing_and_home_textiles",
    "electronicos_articulos_hogar": "electronics_and_home",
    "otros": "other",
}


def ensure_directories() -> None:
    for directory in (RAW_DIR, PORTFOLIO_DATA_DIR, OUTPUT_DIR, MANIFEST_DIR):
        directory.mkdir(parents=True, exist_ok=True)
