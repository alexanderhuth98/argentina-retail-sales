import re
from pathlib import Path

SQL_DIR = Path(__file__).parents[1] / "sql"


def _production_sql() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(SQL_DIR.glob("*.sql"))
        if path.name != "deploy.sql"
    )


def test_sql_server_layer_has_schemas_typed_tables_and_keys():
    sql = _production_sql().lower()

    assert "create schema retail" in sql
    assert "create schema retail_ops" in sql
    for table in (
        "monthly_summary",
        "payment_mix",
        "category_mix",
        "channel_mix",
        "quality_checks",
    ):
        assert f"create table retail.{table}" in sql
        assert f"pk_{table}" in sql
    assert "decimal(28, 8)" in sql
    assert "date not null" in sql
    assert "uniqueidentifier not null" in sql


def test_sql_load_is_atomic_idempotent_and_quality_gated():
    load_sql = (SQL_DIR / "02_load_portfolio.sql").read_text(encoding="utf-8").lower()

    assert "create or alter procedure retail_ops.load_portfolio_csvs" in load_sql
    assert load_sql.count("bulk insert #") == 5
    assert "begin transaction" in load_sql
    assert "commit transaction" in load_sql
    assert "rollback transaction" in load_sql
    assert "sp_getapplock" in load_sql
    assert "every high source check must be present and pass" in load_sql
    assert load_sql.index("every high source check") < load_sql.index(
        "delete from retail.channel_mix"
    )
    assert "merge " not in load_sql


def test_sql_uses_explicit_projections_ctes_windows_and_indexes():
    sql = _production_sql()

    assert not re.search(r"\bSELECT\s+(?:\w+\.)?\*", sql, flags=re.IGNORECASE)
    assert "WITH latest_month_by_format AS" in sql
    assert "LAG(payment.share_pct, 12) OVER" in sql
    assert "NULLIF(history.prior_year_sales_thousand_ars, 0)" in sql
    assert sql.count("CREATE NONCLUSTERED INDEX") == 5
