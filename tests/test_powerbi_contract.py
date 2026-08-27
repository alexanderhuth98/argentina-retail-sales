import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
POWERBI = ROOT / "powerbi"
MODEL_PATH = POWERBI / "ArgentinaRetail.SemanticModel" / "model.bim"
PAGES = POWERBI / "ArgentinaRetail.Report" / "definition" / "pages"


def _model() -> dict:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))["model"]


def test_all_pbip_json_is_parseable_and_connection_is_safe():
    json_paths = list(POWERBI.rglob("*.json"))
    json_paths.extend(
        [
            POWERBI / "ArgentinaRetail.pbip",
            POWERBI / "ArgentinaRetail.Report" / ".platform",
            POWERBI / "ArgentinaRetail.Report" / "definition.pbir",
            POWERBI / "ArgentinaRetail.SemanticModel" / ".platform",
            POWERBI / "ArgentinaRetail.SemanticModel" / "definition.pbism",
            MODEL_PATH,
        ]
    )
    for path in json_paths:
        json.loads(path.read_text(encoding="utf-8"))

    model_text = MODEL_PATH.read_text(encoding="utf-8")
    assert not re.search(r"(?i)[a-z]:\\|/users/|/home/", model_text)
    assert not re.search(r"(?i)password\s*=|pwd\s*=|user\s*id\s*=|uid\s*=", model_text)
    assert "ServerName" in model_text
    assert "DatabaseName" in model_text


def test_semantic_model_matches_csv_contracts_and_star_schema():
    model = _model()
    tables = {table["name"]: table for table in model["tables"]}
    source_files = {
        "monthly_summary": "monthly_summary.csv",
        "payment_mix": "payment_mix.csv",
        "category_mix": "category_mix.csv",
        "channel_mix": "channel_mix.csv",
        "quality_checks": "quality_checks.csv",
    }
    assert set(source_files) <= tables.keys()
    assert {"Calendario", "Formato", "MedioPago", "Categoria", "Canal", "Medidas"} <= tables.keys()

    for table_name, file_name in source_files.items():
        with (ROOT / "portfolio_data" / file_name).open(encoding="utf-8", newline="") as source:
            headers = next(csv.reader(source))
        source_columns = {column["sourceColumn"] for column in tables[table_name]["columns"]}
        assert source_columns <= set(headers)

    relationships = model["relationships"]
    assert len(relationships) == 12
    assert all("crossFilteringBehavior" not in relationship for relationship in relationships)
    assert not any(
        relationship["fromTable"] in source_files and relationship["toTable"] in source_files
        for relationship in relationships
    )


def test_business_measures_require_one_format_and_cover_dashboard_units():
    measures_table = next(table for table in _model()["tables"] if table["name"] == "Medidas")
    measures = {measure["name"]: measure for measure in measures_table["measures"]}

    assert len(measures) >= 30
    assert "HASONEVALUE('Formato'[format_key])" in measures["Formato unico"]["expression"]
    for name in (
        "Ventas nominales",
        "Indice real",
        "Share pago",
        "Ventas categoria",
        "Share canal",
    ):
        assert "[Formato unico] = 1" in measures[name]["expression"]
    assert measures["Variacion real interanual"]["formatString"] == "0.0%"
    assert "pp" in measures["Cambio pago interanual pp"]["formatString"]
    assert "'quality_checks'[severity] = \"HIGH\"" in measures["Gate publicacion"]["expression"]


def test_report_has_four_pages_kpi_trend_breakdown_and_valid_references():
    model = _model()
    fields = {
        table["name"]: {
            *(column["name"] for column in table.get("columns", [])),
            *(measure["name"] for measure in table.get("measures", [])),
        }
        for table in model["tables"]
    }
    expected_pages = {
        "Panorama ejecutivo",
        "Medios de pago",
        "Categorias",
        "Canales y calidad",
    }
    page_files = list(PAGES.glob("*/page.json"))
    assert {json.loads(path.read_text(encoding="utf-8"))["displayName"] for path in page_files} == (
        expected_pages
    )

    for page_file in page_files:
        visuals = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (page_file.parent / "visuals").glob("*/visual.json")
        ]
        assert len(visuals) >= 8
        cards = [visual for visual in visuals if visual["visual"]["visualType"] == "card"]
        assert len(cards) >= 4
        assert all(card["position"]["y"] < 210 for card in cards)
        assert any(visual["visual"]["visualType"] == "lineChart" for visual in visuals)
        assert any(visual["position"]["y"] >= 490 for visual in visuals)

        for visual in visuals:
            text = json.dumps(visual, ensure_ascii=False, separators=(",", ":"))
            for entity, field in re.findall(r'"queryRef":"([^.]+)\.([^"]+)"', text):
                assert entity in fields
                assert field in fields[entity]
