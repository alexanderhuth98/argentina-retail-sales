"""Build the static, interactive portfolio dashboard from curated CSV marts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from . import config

REQUIRED_COLUMNS = {
    "monthly_summary": {
        "month",
        "retail_format",
        "nominal_sales_million_ars",
        "real_sales_index_original",
        "real_sales_index_sa",
        "real_sales_index_trend",
        "real_sales_yoy_pct",
        "real_sales_sa_mom_pct",
    },
    "payment_mix": {
        "month",
        "retail_format",
        "payment_method",
        "sales_thousand_ars",
        "share_pct",
        "is_observed",
    },
    "category_mix": {
        "month",
        "retail_format",
        "category",
        "sales_thousand_ars",
        "share_pct",
        "is_observed",
    },
    "channel_mix": {
        "month",
        "retail_format",
        "channel",
        "sales_thousand_ars",
        "share_pct",
        "is_observed",
    },
    "quality_checks": {"source", "check", "severity", "status", "detail"},
}


class DashboardContractError(ValueError):
    """Raised when a curated mart cannot safely drive the dashboard."""


def quality_gate(checks: pd.DataFrame | list[dict[str, Any]]) -> str:
    """Return PASS only when at least one HIGH check exists and all HIGH checks pass."""
    frame = checks if isinstance(checks, pd.DataFrame) else pd.DataFrame(checks)
    if not {"severity", "status"}.issubset(frame.columns):
        return "BLOCKED"
    high = frame.loc[frame["severity"].astype(str).str.upper().eq("HIGH")]
    if high.empty or not high["status"].astype(str).str.upper().eq("PASS").all():
        return "BLOCKED"
    return "PASS"


def add_group_yoy(
    frame: pd.DataFrame,
    dimension_column: str,
    value_column: str,
    output_column: str,
    *,
    percentage: bool,
) -> pd.DataFrame:
    """Add a 12-month comparison within format and business dimension."""
    result = frame.sort_values(["retail_format", dimension_column, "month"]).copy()
    group_columns = ["retail_format", dimension_column]
    previous = result.groupby(group_columns, sort=False)[value_column].shift(12)
    if percentage:
        result[output_column] = (result[value_column] / previous - 1) * 100
    else:
        result[output_column] = result[value_column] - previous
    return result.sort_index()


def _load_frame(data_dir: Path, name: str) -> pd.DataFrame:
    path = data_dir / f"{name}.csv"
    if not path.exists():
        raise DashboardContractError(f"Falta el mart curado: {path.name}")
    frame = pd.read_csv(path)
    missing = REQUIRED_COLUMNS[name].difference(frame.columns)
    if missing:
        raise DashboardContractError(f"Columnas faltantes en {path.name}: {sorted(missing)}")
    if "month" in frame:
        frame["month"] = pd.to_datetime(frame["month"], errors="raise")
    if "retail_format" in frame:
        formats = set(frame["retail_format"].dropna().unique())
        if not formats.issubset({"supermarkets", "wholesale"}):
            raise DashboardContractError(f"Formato inesperado en {path.name}: {sorted(formats)}")
    return frame


def load_dashboard_data(data_dir: Path = config.PORTFOLIO_DATA_DIR) -> dict[str, pd.DataFrame]:
    """Load the five versioned presentation marts and derive explicit UI metrics."""
    data_dir = Path(data_dir)
    frames = {name: _load_frame(data_dir, name) for name in REQUIRED_COLUMNS}
    frames["payment_mix"] = add_group_yoy(
        frames["payment_mix"],
        "payment_method",
        "share_pct",
        "share_yoy_pp",
        percentage=False,
    )
    frames["category_mix"] = add_group_yoy(
        frames["category_mix"],
        "category",
        "sales_thousand_ars",
        "nominal_sales_yoy_pct",
        percentage=True,
    )
    return frames


def _snapshot_date(manifest_path: Path | None) -> str:
    if manifest_path is None or not manifest_path.exists():
        return "No disponible"
    dates = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            dates.append(json.loads(line)["retrieved_at"][:10])
    return max(dates) if dates else "No disponible"


def _json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "item"):
        return value.item()
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {column: _json_value(value) for column, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def build_dashboard_payload(
    data_dir: Path = config.PORTFOLIO_DATA_DIR,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Return browser-ready data without non-standard JSON numeric values."""
    frames = load_dashboard_data(data_dir)
    monthly = frames["monthly_summary"]
    latest = monthly["month"].max()
    if manifest_path is None and Path(data_dir).resolve() == config.PORTFOLIO_DATA_DIR.resolve():
        manifest_path = config.MANIFEST_DIR / "raw_sources.jsonl"
    payload = {name: _records(frame) for name, frame in frames.items()}
    payload["metadata"] = {
        "latest_month": latest.strftime("%Y-%m-%d"),
        "snapshot_date": _snapshot_date(manifest_path),
        "years": sorted(monthly["month"].dt.year.unique().tolist()),
        "row_count": sum(len(frame) for frame in frames.values()),
        "gate": quality_gate(frames["quality_checks"]),
        "source": "INDEC / Datos Argentina",
        "data_license": "CC BY 4.0",
    }
    return payload


def _safe_json(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return serialized.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


CSS = r"""
:root{--paper:#F5F1E8;--card:#FFFEFA;--ink:#183044;--muted:#5B6D77;--super:#164B73;--whole:#B65F45;--teal:#246864;--ochre:#D2A449;--focus:#765600;--line:#D8D2C7;--danger:#A52828;--shadow:0 8px 24px rgba(24,48,68,.08);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink);background:var(--paper)}
*{box-sizing:border-box}html{scroll-behavior:smooth;max-width:100%;overflow-x:hidden}body{margin:0;background:var(--paper);max-width:100%;overflow-x:hidden}button,select,input{font:inherit;color:inherit}button,select,.format-option{min-height:44px}.skip-link{position:absolute;left:12px;top:-80px;padding:10px 14px;background:var(--ink);color:#fff;z-index:20}.skip-link:focus{top:12px}a{color:var(--super)}:focus-visible{outline:3px solid var(--ochre);outline-offset:3px}.shell{width:min(1280px,calc(100% - 32px));margin:0 auto;padding:24px 0 40px}.masthead{display:grid;grid-template-columns:1fr auto;gap:20px;align-items:end;margin-bottom:18px}.eyebrow{margin:0 0 7px;color:var(--teal);font-size:.76rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.masthead h1{margin:0;font-family:Georgia,serif;font-size:clamp(2rem,4vw,3.65rem);line-height:.96;letter-spacing:-.035em}.dek{max-width:710px;margin:12px 0 0;color:var(--muted);font-size:1rem}.snapshot{border-left:3px solid var(--ochre);padding-left:14px;font-size:.82rem;line-height:1.6;color:var(--muted);white-space:nowrap}.gate-banner{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:11px 16px;margin:0 0 14px;border:1px solid #B8CEC8;border-radius:10px;background:#EDF5F1;color:#245B50;font-weight:700}.gate-banner.blocked{border-color:#D9A5A5;background:#FBECEC;color:var(--danger)}.toolbar{position:sticky;top:0;z-index:10;display:grid;grid-template-columns:minmax(300px,1fr) 180px auto;gap:14px;align-items:end;padding:14px;margin-bottom:12px;border:1px solid var(--line);border-radius:12px;background:rgba(255,254,250,.97);box-shadow:var(--shadow)}fieldset{min-width:0;margin:0;padding:0;border:0}legend,.field-label{display:block;margin:0 0 7px;font-size:.75rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase}.format-options{display:grid;grid-template-columns:1fr 1fr;gap:8px}.format-option{position:relative;display:flex;align-items:center;justify-content:center;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:#fff;cursor:pointer;font-weight:750;text-align:center}.format-option input{position:absolute;opacity:0;pointer-events:none}.format-option:has(input:checked){color:#fff;border-color:var(--format-color);background:var(--format-color)}select,.reset{width:100%;padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:#fff}.reset{width:auto;padding-inline:18px;background:var(--ink);color:#fff;border-color:var(--ink);cursor:pointer}.tabbar{display:flex;gap:7px;padding:5px;margin-bottom:18px;overflow-x:auto;border-bottom:1px solid var(--line);scrollbar-width:thin}.tab{flex:0 0 auto;padding:9px 14px;border:0;border-bottom:3px solid transparent;background:transparent;cursor:pointer;font-weight:750;color:var(--muted)}.tab[aria-selected=true]{border-color:var(--format-color);color:var(--ink)}.view[hidden]{display:none}.section-head{display:flex;justify-content:space-between;gap:18px;align-items:end;margin:0 0 14px}.section-head h2{margin:0;font-family:Georgia,serif;font-size:clamp(1.55rem,2.6vw,2.2rem)}.section-head p{max-width:660px;margin:5px 0 0;color:var(--muted)}.effective{font-size:.8rem;color:var(--muted);text-align:right}.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:12px}.kpi{min-width:0;padding:16px;border:1px solid var(--line);border-top:4px solid var(--format-color);border-radius:10px;background:var(--card);box-shadow:var(--shadow)}.kpi-label{min-height:34px;margin:0;color:var(--muted);font-size:.77rem;font-weight:750;letter-spacing:.025em}.kpi-value{display:block;margin-top:8px;font-family:Georgia,serif;font-size:clamp(1.42rem,2.6vw,2.18rem);line-height:1.1;overflow-wrap:anywhere}.kpi-note{display:block;min-height:18px;margin-top:7px;color:var(--muted);font-size:.73rem}.chart-grid{display:grid;grid-template-columns:3fr 2fr;gap:12px;margin-bottom:12px}.chart-grid.equal{grid-template-columns:1fr 1fr}.card{min-width:0;border:1px solid var(--line);border-radius:10px;background:var(--card);box-shadow:var(--shadow)}.card-head{padding:15px 16px 0}.card h3{margin:0;font-size:.96rem}.card-sub{margin:4px 0 0;color:var(--muted);font-size:.75rem}.chart{width:100%;min-width:0;height:310px;padding:8px}.chart-fallback,.empty-chart{display:flex;height:100%;align-items:center;justify-content:center;padding:24px;color:var(--muted);text-align:center;border:1px dashed var(--line);border-radius:8px;background:#FAF8F2}.local-filter{display:flex;gap:10px;align-items:end;margin-bottom:12px;padding:13px 16px}.local-filter label{flex:1}.local-filter select{margin-top:7px}.notice{margin:0 0 12px;padding:12px 16px;border-left:4px solid var(--ochre);background:#FBF4DE;color:#5A4B21;font-size:.86rem}.coverage{border-left-color:var(--teal);background:#EAF4F2;color:#214E4B}.table-wrap{max-width:100%;overflow-x:auto;border-radius:10px}.quality-table{width:100%;border-collapse:collapse;font-size:.82rem}.quality-table caption{padding:14px 16px;text-align:left;font-weight:800}.quality-table th,.quality-table td{padding:11px 12px;border-top:1px solid var(--line);text-align:left;vertical-align:top}.quality-table th{background:#F8F5EE;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em}.status-pass{font-weight:800;color:#23675B}.status-fail{font-weight:800;color:var(--danger)}details.data-summary{margin:0 16px 14px;color:var(--muted);font-size:.8rem}details.data-summary summary{min-height:44px;padding:12px 0;cursor:pointer;font-weight:700}.summary-list{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin:0;padding-left:20px}.status-line{min-height:24px;margin:10px 0;color:var(--muted);font-size:.78rem}.status-line.error{color:var(--danger);font-weight:800}.site-footer{display:grid;grid-template-columns:2fr 1fr;gap:20px;margin-top:22px;padding:20px 0;border-top:1px solid var(--line);color:var(--muted);font-size:.78rem;line-height:1.55}.site-footer p{margin:0}.mobile .shell{width:min(100% - 20px,680px);padding-top:14px}.mobile .masthead,.mobile .site-footer{grid-template-columns:1fr}.mobile .snapshot{white-space:normal}.mobile .toolbar{position:static;grid-template-columns:1fr}.mobile .reset{width:100%}.mobile .kpis,.mobile .chart-grid,.mobile .chart-grid.equal{grid-template-columns:1fr}.mobile .section-head{display:block}.mobile .effective{text-align:left;margin-top:7px}.mobile .chart{height:280px}.mobile .summary-list{grid-template-columns:1fr}
:focus-visible{outline-color:var(--focus)}
body.mobile .shell{width:min(100% - 20px,680px);padding-top:14px}body.mobile .masthead,body.mobile .site-footer{grid-template-columns:1fr}body.mobile .masthead h1{font-size:2rem;overflow-wrap:anywhere}body.mobile .snapshot{white-space:normal}body.mobile .toolbar{position:static;grid-template-columns:1fr}body.mobile .format-options{grid-template-columns:1fr}body.mobile .reset{width:100%}body.mobile .tabbar{display:grid;grid-template-columns:1fr 1fr;overflow:visible}body.mobile .tab{white-space:normal}body.mobile .kpis,body.mobile .chart-grid,body.mobile .chart-grid.equal{grid-template-columns:1fr}body.mobile .section-head{display:block}body.mobile .effective{text-align:left;margin-top:7px}body.mobile .chart{height:280px}body.mobile .summary-list{grid-template-columns:1fr}body.mobile .quality-table{min-width:620px}
@media(max-width:760px){.shell{width:min(100% - 20px,680px);padding-top:14px}.masthead,.site-footer{grid-template-columns:1fr}.masthead h1{font-size:2rem;overflow-wrap:anywhere}.snapshot{white-space:normal}.toolbar{position:static;grid-template-columns:1fr}.format-options{grid-template-columns:1fr}.reset{width:100%}.tabbar{display:grid;grid-template-columns:1fr 1fr;overflow:visible}.tab{white-space:normal}.kpis,.chart-grid,.chart-grid.equal{grid-template-columns:1fr}.section-head{display:block}.effective{text-align:left;margin-top:7px}.chart{height:280px}.summary-list{grid-template-columns:1fr}.quality-table{min-width:620px}}
@media(max-width:360px){.shell{width:calc(100% - 16px)}.format-options{grid-template-columns:1fr}.masthead h1{font-size:1.85rem}.kpi{padding:14px}.tab{padding-inline:10px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
"""


BODY = r"""
<a class="skip-link" href="#contenido">Saltar al contenido</a>
<div class="shell">
  <header class="masthead">
    <div><p class="eyebrow">Monitor mensual · Argentina</p><h1>Pulso del retail argentino</h1><p class="dek">Ventas reales, composición nominal y cobertura estadística para decidir sin mezclar universos de encuesta.</p></div>
    <div class="snapshot" aria-label="Metadatos"><strong>Corte:</strong> <span id="meta-cutoff"></span><br><strong>Snapshot:</strong> <span id="meta-snapshot"></span><br><strong>Fuente:</strong> INDEC / Datos Argentina</div>
  </header>
  <div id="gate-banner" class="gate-banner" role="status"><span id="gate-copy"></span><strong id="gate-value"></strong></div>
  <form class="toolbar" aria-label="Filtros globales" onsubmit="return false">
    <fieldset><legend>Formato obligatorio</legend><div class="format-options">
      <label class="format-option" style="--format-color:#164B73"><input type="radio" name="retail-format" value="supermarkets" checked>Supermercados</label>
      <label class="format-option" style="--format-color:#B65F45"><input type="radio" name="retail-format" value="wholesale">Autoservicios mayoristas</label>
    </div></fieldset>
    <label><span class="field-label">Período / año</span><select id="year-filter" aria-label="Seleccionar período"></select></label>
    <button id="reset-filters" class="reset" type="button">Restablecer filtros</button>
  </form>
  <nav class="tabbar" aria-label="Vistas del dashboard" role="tablist">
    <button class="tab" id="tab-overview" role="tab" aria-controls="overview" aria-selected="true" data-view="overview">Panorama</button>
    <button class="tab" id="tab-payments" role="tab" aria-controls="payments" aria-selected="false" data-view="payments">Medios de pago</button>
    <button class="tab" id="tab-categories" role="tab" aria-controls="categories" aria-selected="false" data-view="categories">Categorías</button>
    <button class="tab" id="tab-channels" role="tab" aria-controls="channels" aria-selected="false" data-view="channels">Canales y calidad</button>
  </nav>
  <main id="contenido">
    <section id="overview" class="view" role="tabpanel" aria-labelledby="tab-overview">
      <header class="section-head"><div><h2>Panorama</h2><p>¿La facturación corriente coincide con una recuperación real?</p></div><div class="effective" id="overview-date"></div></header>
      <div class="kpis">
        <article class="kpi"><p class="kpi-label">Índice real original</p><strong class="kpi-value" id="real-index">—</strong><small class="kpi-note">base 2017 = 100</small></article>
        <article class="kpi"><p class="kpi-label">Variación real interanual</p><strong class="kpi-value" id="real-yoy">—</strong><small class="kpi-note">% vs. igual mes del año anterior</small></article>
        <article class="kpi"><p class="kpi-label">Variación real mensual SA</p><strong class="kpi-value" id="real-mom">—</strong><small class="kpi-note">% vs. mes anterior</small></article>
        <article class="kpi"><p class="kpi-label">Ventas nominales</p><strong class="kpi-value" id="nominal-sales">—</strong><small class="kpi-note">millones ARS corrientes</small></article>
      </div>
      <div class="chart-grid"><article class="card"><div class="card-head"><h3>Actividad real</h3><p class="card-sub">Índice original y tendencia-ciclo · base 2017 = 100</p></div><div id="overview-index-chart" class="chart" role="img" aria-label="Evolución del índice real original y tendencia"><p class="chart-fallback">Gráfico no disponible. Los valores principales permanecen en las tarjetas.</p></div><details class="data-summary"><summary>Resumen accesible del gráfico</summary><ul id="overview-index-summary" class="summary-list"></ul></details></article>
      <article class="card"><div class="card-head"><h3>Facturación nominal</h3><p class="card-sub">Millones ARS corrientes · eje separado</p></div><div id="overview-sales-chart" class="chart" role="img" aria-label="Evolución de ventas nominales"><p class="chart-fallback">Gráfico no disponible. Consulte la tarjeta de ventas nominales.</p></div><details class="data-summary"><summary>Resumen accesible del gráfico</summary><ul id="overview-sales-summary" class="summary-list"></ul></details></article></div>
    </section>
    <section id="payments" class="view" role="tabpanel" aria-labelledby="tab-payments" hidden>
      <header class="section-head"><div><h2>Medios de pago</h2><p>Participación dentro del formato seleccionado; los cambios se expresan en puntos porcentuales.</p></div><div class="effective" id="payments-date"></div></header>
      <div id="payment-kpis" class="kpis"></div>
      <div class="chart-grid"><article class="card"><div class="card-head"><h3>Evolución del mix</h3><p class="card-sub">Participación mensual (%)</p></div><div id="payments-line-chart" class="chart" role="img" aria-label="Evolución de la participación por medio de pago"><p class="chart-fallback">Gráfico no disponible. Consulte las participaciones actuales.</p></div><details class="data-summary"><summary>Resumen accesible del último mes</summary><ul id="payments-summary" class="summary-list"></ul></details></article><article class="card"><div class="card-head"><h3>Cambio interanual</h3><p class="card-sub">Puntos porcentuales (pp)</p></div><div id="payments-delta-chart" class="chart" role="img" aria-label="Cambio interanual de participación por medio de pago"><p class="chart-fallback">Gráfico no disponible. Los cambios figuran en las tarjetas.</p></div></article></div>
    </section>
    <section id="categories" class="view" role="tabpanel" aria-labelledby="tab-categories" hidden>
      <header class="section-head"><div><h2>Categorías</h2><p>Evolución nominal y participación dentro de cada formato.</p></div><div class="effective" id="categories-date"></div></header>
      <div class="card local-filter"><label><span class="field-label">Categoría destacada</span><select id="category-filter"></select></label></div>
      <p class="notice"><strong>Lectura responsable:</strong> la variación nominal por categoría no equivale a volumen ni descuenta inflación.</p>
      <div class="kpis">
        <article class="kpi"><p class="kpi-label">Ventas nominales · categoría</p><strong class="kpi-value" id="category-sales">—</strong><small class="kpi-note">millones ARS corrientes</small></article>
        <article class="kpi"><p class="kpi-label">Share de categoría</p><strong class="kpi-value" id="category-share">—</strong><small class="kpi-note">% dentro del formato</small></article>
        <article class="kpi"><p class="kpi-label">Variación nominal interanual</p><strong class="kpi-value" id="category-yoy">—</strong><small class="kpi-note">% nominal</small></article>
        <article class="kpi"><p class="kpi-label">Fecha efectiva</p><strong class="kpi-value" id="category-date">—</strong><small class="kpi-note">último mes observado</small></article>
      </div>
      <div class="chart-grid equal"><article class="card"><div class="card-head"><h3>Evolución del mix</h3><p class="card-sub">Share mensual (%) · la categoría elegida se destaca</p></div><div id="categories-mix-chart" class="chart" role="img" aria-label="Evolución del mix de categorías"><p class="chart-fallback">Gráfico no disponible. Consulte el ranking del último mes.</p></div></article><article class="card"><div class="card-head"><h3>Ranking del último mes</h3><p class="card-sub">Participación (%)</p></div><div id="categories-ranking-chart" class="chart" role="img" aria-label="Ranking de categorías del último mes"><p class="chart-fallback">Gráfico no disponible. Consulte el resumen accesible.</p></div><details class="data-summary"><summary>Ranking en texto</summary><ol id="categories-summary"></ol></details></article></div>
    </section>
    <section id="channels" class="view" role="tabpanel" aria-labelledby="tab-channels" hidden>
      <header class="section-head"><div><h2>Canales y calidad</h2><p>Cobertura observada, mix online/salón y controles previos a publicación.</p></div><div class="effective" id="channels-period"></div></header>
      <div class="kpis">
        <article class="kpi"><p class="kpi-label">Share online</p><strong class="kpi-value" id="online-share">—</strong><small class="kpi-note" id="online-note">% observado</small></article>
        <article class="kpi"><p class="kpi-label">Última fecha observada</p><strong class="kpi-value" id="channel-date">—</strong><small class="kpi-note">detalle de canal</small></article>
        <article class="kpi"><p class="kpi-label">Fallas HIGH</p><strong class="kpi-value" id="high-fails">—</strong><small class="kpi-note">controles bloqueantes</small></article>
        <article class="kpi"><p class="kpi-label">Gate de publicación</p><strong class="kpi-value" id="quality-gate">—</strong><small class="kpi-note">requiere ≥1 HIGH y 0 fallas</small></article>
      </div>
      <p id="channel-coverage" class="notice coverage"></p>
      <article class="card"><div class="card-head"><h3>Canal online / salón</h3><p class="card-sub">Participación mensual (%) · los faltantes no se imputan como cero</p></div><div id="channels-chart" class="chart" role="img" aria-label="Evolución de participación online y salón"><p class="chart-fallback">Gráfico no disponible. Consulte la fecha efectiva y la nota de cobertura.</p></div><details class="data-summary"><summary>Resumen accesible</summary><ul id="channels-summary" class="summary-list"></ul></details></article>
      <article class="card" style="margin-top:12px"><div class="table-wrap"><table class="quality-table"><caption>Los 11 controles del snapshot</caption><thead><tr><th scope="col">Fuente</th><th scope="col">Severidad</th><th scope="col">Estado</th><th scope="col">Control</th><th scope="col">Detalle</th></tr></thead><tbody id="quality-body"></tbody></table></div></article>
    </section>
  </main>
  <p id="app-status" class="status-line" role="status" aria-live="polite">Cargando visualizaciones…</p>
  <footer class="site-footer"><p><strong>Contexto:</strong> supermercados y autoservicios mayoristas son universos distintos; nunca se suman. 2026 es parcial. El canal mayorista posterior a agosto de 2022 es no observado, no cero.</p><p>Fuente: INDEC / Datos Argentina · Datos: CC BY 4.0 · Código: MIT.</p></footer>
</div>
"""


JS = r"""
(()=>{'use strict';
let DATA;
const $=id=>document.getElementById(id);
const LABELS={supermarkets:'Supermercados',wholesale:'Autoservicios mayoristas',cash:'Efectivo',debit_card:'Tarjeta de débito',credit_card:'Tarjeta de crédito',other:'Otros',beverages:'Bebidas',grocery:'Almacén',bakery:'Panadería',dairy:'Lácteos',meat:'Carnes',fruit_and_vegetables:'Verdulería y frutería',prepared_food:'Alimentos preparados / rotisería',cleaning_and_personal_care:'Limpieza y perfumería',clothing_and_home_textiles:'Indumentaria y textiles',electronics_and_home:'Electrónicos y hogar',online:'Online',showroom:'Salón'};
const COLORS={supermarkets:'#164B73',wholesale:'#B65F45',cash:'#246864',debit_card:'#9A6B00',credit_card:'#164B73',other:'#8A6F62',online:'#246864',showroom:'#9A6B00'};
const state={format:'supermarkets',year:'',category:'grocery',view:'overview'};
const valid=value=>value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value));
const fmt=(value,digits=1)=>valid(value)?new Intl.NumberFormat('es-AR',{minimumFractionDigits:digits,maximumFractionDigits:digits}).format(Number(value)):'No disponible';
const signed=(value,unit)=>valid(value)?`${Number(value)>0?'+':''}${fmt(value,1)}${unit}`:'No disponible';
const month=value=>value?new Intl.DateTimeFormat('es-AR',{month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(`${value}T00:00:00`)):'No disponible';
const periodRows=rows=>rows.filter(row=>row.retail_format===state.format&&(state.year==='all'||row.month.startsWith(state.year)));
const latestDate=rows=>rows.length?rows.reduce((a,b)=>a.month>b.month?a:b).month:null;
const setText=(id,value)=>{$(id).textContent=value};
const latestRows=rows=>{const date=latestDate(rows);return rows.filter(row=>row.month===date)};
const layout=(ytitle,extra={})=>({paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{family:'Inter, system-ui, sans-serif',color:'#183044',size:11},margin:{l:52,r:18,t:18,b:44},xaxis:{gridcolor:'#E7E1D7',tickformat:'%b\n%Y',dtick:state.year==='all'?'M12':'M1',fixedrange:true},yaxis:{title:ytitle,gridcolor:'#E7E1D7',zerolinecolor:'#C7BFB2',fixedrange:true},legend:{orientation:'h',y:-.2},hoverlabel:{bgcolor:'#FFFEFA'},...extra});
function plot(id,traces,chartLayout){const node=$(id);if(!window.Plotly)return;node.replaceChildren();window.Plotly.react(node,traces,chartLayout,{responsive:true,displayModeBar:false,displaylogo:false});}
function emptyChart(id,message){const node=$(id);if(window.Plotly)window.Plotly.purge(node);node.replaceChildren(Object.assign(document.createElement('p'),{className:'empty-chart',textContent:message}));}
function list(id,items){const node=$(id);node.replaceChildren(...items.map(text=>Object.assign(document.createElement('li'),{textContent:text})));}
function renderOverview(){const rows=periodRows(DATA.monthly_summary);const current=latestRows(rows)[0];setText('overview-date',current?`Fecha efectiva: ${month(current.month)}`:'Sin observaciones para el período');setText('real-index',current?fmt(current.real_sales_index_original,1):'No observado');setText('real-yoy',current?signed(current.real_sales_yoy_pct,'%'):'No observado');setText('real-mom',current?signed(current.real_sales_sa_mom_pct,'%'):'No observado');setText('nominal-sales',current?fmt(current.nominal_sales_million_ars,0):'No observado');if(!rows.length){emptyChart('overview-index-chart','Sin datos para la selección.');emptyChart('overview-sales-chart','Sin datos para la selección.');return}const color=COLORS[state.format];plot('overview-index-chart',[{x:rows.map(r=>r.month),y:rows.map(r=>r.real_sales_index_original),name:'Original',type:'scatter',mode:'lines',line:{color,width:3}},{x:rows.map(r=>r.month),y:rows.map(r=>r.real_sales_index_trend),name:'Tendencia-ciclo',type:'scatter',mode:'lines',line:{color:'#D2A449',width:2,dash:'dot'}}],layout('Índice base 2017=100'));plot('overview-sales-chart',[{x:rows.map(r=>r.month),y:rows.map(r=>r.nominal_sales_million_ars),name:'Ventas',type:'bar',marker:{color}}],layout('Millones ARS',{showlegend:false}));list('overview-index-summary',[`Inicio: ${month(rows[0].month)}, índice ${fmt(rows[0].real_sales_index_original,1)}.`,`Último: ${month(current.month)}, índice ${fmt(current.real_sales_index_original,1)}.`,`Tendencia último mes: ${fmt(current.real_sales_index_trend,1)}.`]);list('overview-sales-summary',[`Último mes: ${month(current.month)}.`,`Ventas nominales: ${fmt(current.nominal_sales_million_ars,0)} millones ARS.`]);}
function renderPayments(){const rows=periodRows(DATA.payment_mix).filter(r=>r.is_observed);const current=latestRows(rows);const date=latestDate(rows);setText('payments-date',date?`Fecha efectiva: ${month(date)}`:'Sin observaciones');const methods=['cash','debit_card','credit_card','other'];const cards=methods.map(method=>{const row=current.find(r=>r.payment_method===method);const article=document.createElement('article');article.className='kpi';const label=document.createElement('p');label.className='kpi-label';label.textContent=LABELS[method];const value=document.createElement('strong');value.className='kpi-value';value.textContent=row?`${fmt(row.share_pct,1)}%`:'No observado';const note=document.createElement('small');note.className='kpi-note';note.textContent=row&&Number.isFinite(Number(row.share_yoy_pp))?`${signed(row.share_yoy_pp,' pp')} interanual`:'Sin comparación interanual';article.append(label,value,note);return article});$('payment-kpis').replaceChildren(...cards);if(!rows.length){emptyChart('payments-line-chart','Sin observaciones para el período.');emptyChart('payments-delta-chart','Sin comparación disponible.');list('payments-summary',['Sin observaciones para la selección.']);return}plot('payments-line-chart',methods.map(method=>({x:rows.filter(r=>r.payment_method===method).map(r=>r.month),y:rows.filter(r=>r.payment_method===method).map(r=>r.share_pct),name:LABELS[method],type:'scatter',mode:'lines',line:{color:COLORS[method],width:2.5}})),layout('Participación (%)'));const deltas=methods.map(method=>current.find(r=>r.payment_method===method)?.share_yoy_pp??null);plot('payments-delta-chart',[{x:methods.map(m=>LABELS[m]),y:deltas,type:'bar',marker:{color:deltas.map(v=>v!==null&&v<0?'#8A6F62':'#2D7C78')}}],layout('Cambio (pp)',{showlegend:false,xaxis:{fixedrange:true,tickangle:-18}}));list('payments-summary',current.map(row=>`${LABELS[row.payment_method]}: ${fmt(row.share_pct,1)}%; cambio ${signed(row.share_yoy_pp,' pp')}.`));}
function renderCategories(){const allFormat=DATA.category_mix.filter(r=>r.retail_format===state.format&&r.is_observed);const available=[...new Set(allFormat.map(r=>r.category))];if(!available.includes(state.category))state.category=available[0];const select=$('category-filter');select.replaceChildren(...available.map(category=>{const option=document.createElement('option');option.value=category;option.textContent=LABELS[category]||category;option.selected=category===state.category;return option}));const rows=periodRows(DATA.category_mix).filter(r=>r.is_observed);const date=latestDate(rows);const current=rows.find(r=>r.month===date&&r.category===state.category);setText('categories-date',date?`Fecha efectiva: ${month(date)}`:'Sin observaciones');setText('category-sales',current?fmt(current.sales_thousand_ars/1000,0):'No observado');setText('category-share',current?`${fmt(current.share_pct,1)}%`:'No observado');setText('category-yoy',current?signed(current.nominal_sales_yoy_pct,'%'):'No disponible');setText('category-date',current?month(current.month):'No observado');if(!rows.length){emptyChart('categories-mix-chart','Sin observaciones para el período.');emptyChart('categories-ranking-chart','Sin ranking para el período.');list('categories-summary',['Sin observaciones para la selección.']);return}const categories=[...new Set(rows.map(r=>r.category))];plot('categories-mix-chart',categories.map(category=>{const series=rows.filter(r=>r.category===category);const selected=category===state.category;return{x:series.map(r=>r.month),y:series.map(r=>r.share_pct),name:LABELS[category]||category,type:'scatter',mode:'lines',opacity:selected?1:.42,line:{color:selected?COLORS[state.format]:'#7C8B92',width:selected?4:1.5}}}),layout('Participación (%)'));const ranking=latestRows(rows).sort((a,b)=>a.share_pct-b.share_pct);plot('categories-ranking-chart',[{x:ranking.map(r=>r.share_pct),y:ranking.map(r=>LABELS[r.category]||r.category),type:'bar',orientation:'h',marker:{color:ranking.map(r=>r.category===state.category?COLORS[state.format]:'#AEB8B8')}}],layout('Participación (%)',{showlegend:false,margin:{l:150,r:18,t:18,b:44},xaxis:{gridcolor:'#E7E1D7',fixedrange:true},yaxis:{fixedrange:true,automargin:true}}));const descending=[...ranking].reverse();list('categories-summary',descending.map(r=>`${LABELS[r.category]||r.category}: ${fmt(r.share_pct,1)}%.`));}
function renderChannels(){const formatRows=DATA.channel_mix.filter(r=>r.retail_format===state.format);const rows=periodRows(DATA.channel_mix);const observedToPeriod=formatRows.filter(r=>r.is_observed&&(state.year==='all'||Number(r.month.slice(0,4))<=Number(state.year)));const lastObserved=latestDate(observedToPeriod);const current=formatRows.find(r=>r.month===lastObserved&&r.channel==='online'&&r.is_observed);setText('online-share',current?`${fmt(current.share_pct,2)}%`:'No observado');setText('online-note',current?`% observado en ${month(current.month)}`:'sin imputar cero');setText('channel-date',month(lastObserved));setText('channels-period',state.year==='all'?'Todo el período':`Período ${state.year}`);const highs=DATA.quality_checks.filter(r=>String(r.severity).toUpperCase()==='HIGH');const failures=highs.filter(r=>String(r.status).toUpperCase()!=='PASS').length;setText('high-fails',String(failures));setText('quality-gate',DATA.metadata.gate);const coverage=state.format==='wholesale'?'Mayoristas: el detalle online/salón termina en agosto de 2022. Desde septiembre de 2022 se muestra como no observado, nunca como cero.':'Supermercados: detalle online/salón observado hasta el último mes del corte.';setText('channel-coverage',coverage);const observedRows=rows.filter(r=>r.is_observed);if(!observedRows.length){emptyChart('channels-chart','No observado en este período. Último dato mayorista: agosto de 2022.');list('channels-summary',[coverage]);}else{const channels=['showroom','online'];plot('channels-chart',channels.map(channel=>{const series=rows.filter(r=>r.channel===channel);return{x:series.map(r=>r.month),y:series.map(r=>r.is_observed?r.share_pct:null),connectgaps:false,name:LABELS[channel],type:'scatter',mode:'lines',line:{color:COLORS[channel],width:2.5}}}),layout('Participación (%)'));const currentObserved=latestRows(observedRows);list('channels-summary',currentObserved.map(r=>`${LABELS[r.channel]}: ${fmt(r.share_pct,2)}% en ${month(r.month)}.`));}}
function renderQuality(){const body=$('quality-body');const rows=DATA.quality_checks.map(check=>{const tr=document.createElement('tr');[LABELS[check.source]||check.source,check.severity,check.status,check.check,check.detail].forEach((value,index)=>{const td=document.createElement('td');td.textContent=value;if(index===2)td.className=String(value).toUpperCase()==='PASS'?'status-pass':'status-fail';tr.append(td)});return tr});body.replaceChildren(...rows);}
function update(){document.documentElement.style.setProperty('--format-color',COLORS[state.format]);renderOverview();renderPayments();renderCategories();renderChannels();renderQuality();setText('app-status',window.Plotly?`Datos listos: ${LABELS[state.format]}, ${state.year==='all'?'todo el período':state.year}.`:`Datos listos: ${LABELS[state.format]}; gráficos no disponibles.`);}
function showView(view,focus=false){state.view=view;document.querySelectorAll('.tab').forEach(tab=>{const selected=tab.dataset.view===view;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;if(selected&&focus)tab.focus()});document.querySelectorAll('.view').forEach(section=>section.hidden=section.id!==view);update();}
function init(){state.year=String(DATA.metadata.years.at(-1));setText('meta-cutoff',month(DATA.metadata.latest_month));setText('meta-snapshot',DATA.metadata.snapshot_date==='No disponible'?DATA.metadata.snapshot_date:new Intl.DateTimeFormat('es-AR',{dateStyle:'medium',timeZone:'UTC'}).format(new Date(`${DATA.metadata.snapshot_date}T00:00:00`)));const pass=DATA.metadata.gate==='PASS';$('gate-banner').classList.toggle('blocked',!pass);setText('gate-copy',pass?'Controles HIGH completos: resultados aptos para publicación.':'Gate bloqueado: resultados exploratorios, no publicables.');setText('gate-value',DATA.metadata.gate);const year=$('year-filter');const all=document.createElement('option');all.value='all';all.textContent='Todo el período';year.append(all,...DATA.metadata.years.map(value=>{const option=document.createElement('option');option.value=String(value);option.textContent=value===2026?'2026 · parcial':String(value);option.selected=String(value)===state.year;return option}));document.querySelectorAll('input[name="retail-format"]').forEach(input=>input.addEventListener('change',event=>{state.format=event.target.value;update()}));year.addEventListener('change',event=>{state.year=event.target.value;update()});$('category-filter').addEventListener('change',event=>{state.category=event.target.value;renderCategories()});$('reset-filters').addEventListener('click',()=>{state.format='supermarkets';state.year=String(DATA.metadata.years.at(-1));state.category='grocery';document.querySelector('input[value="supermarkets"]').checked=true;year.value=state.year;showView('overview')});document.querySelectorAll('.tab').forEach(tab=>{tab.addEventListener('click',()=>showView(tab.dataset.view));tab.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();const tabs=[...document.querySelectorAll('.tab')];const next=(tabs.indexOf(tab)+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;showView(tabs[next].dataset.view,true)})});showView('overview');}
window.addEventListener('DOMContentLoaded',()=>{try{DATA=JSON.parse(document.getElementById('dashboard-data').textContent);init()}catch(error){$('app-status').className='status-line error';setText('app-status','No se pudo iniciar el dashboard. Los datos no se presentan como publicables.');console.error(error)}});
})();
"""


def render_dashboard(payload: dict[str, Any], *, mobile: bool = False) -> str:
    """Render one self-contained HTML variant; Plotly is the only runtime dependency."""
    body_class = "mobile" if mobile else "desktop"
    variant = "móvil" if mobile else "escritorio"
    return f"""<!doctype html>
<html lang="es" data-variant="{variant}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Dashboard de ventas reales, pagos, categorías, canales y calidad del retail argentino.">
  <title>Pulso del retail argentino · {variant.capitalize()}</title>
  <style>{CSS}</style>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" defer></script>
</head>
<body class="{body_class}">
{BODY}
<script id="dashboard-data" type="application/json">{_safe_json(payload)}</script>
<script defer>{JS}</script>
</body>
</html>
"""


def export_dashboard(
    data_dir: Path = config.PORTFOLIO_DATA_DIR,
    site_dir: Path = config.SITE_DIR,
) -> tuple[Path, Path]:
    """Generate and version both responsive entry points plus Pages support files."""
    site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)
    manifest = config.MANIFEST_DIR / "raw_sources.jsonl"
    payload = build_dashboard_payload(data_dir, manifest if manifest.exists() else None)
    if payload["metadata"]["gate"] != "PASS":
        raise DashboardContractError("Gate HIGH bloqueado: no se genera el sitio publicable")
    desktop = site_dir / "index.html"
    mobile = site_dir / "mobile.html"
    desktop.write_text(render_dashboard(payload), encoding="utf-8")
    mobile.write_text(render_dashboard(payload, mobile=True), encoding="utf-8")
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")
    (site_dir / "README.md").write_text(
        "# Sitio estático generado\n\n"
        "No edite `index.html` ni `mobile.html` manualmente. Regenerar desde los cinco CSV "
        "curados con:\n\n```powershell\nargentina-retail-sales export\n```\n",
        encoding="utf-8",
    )
    return desktop, mobile
