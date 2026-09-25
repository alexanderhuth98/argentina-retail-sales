"""Build the static, interactive portfolio dashboard from curated CSV marts."""

from __future__ import annotations

import hashlib
import json
import shutil
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

ASSET_SOURCE_DIR = Path(__file__).with_name("assets")
ASSET_HASHES = {
    "plotly-basic-2.35.2.min.js": "138c2e81014b979dc00867a93da55b7605a17495ee78dd7afb433b7f021dfcfa",
    "plotly-locale-es-2.35.2.js": "1a20051d1983e522718de67dc977fe095727b6ff89bbe4a3c8c6251df841e981",
    "fonts/space-grotesk-variable.ttf": (
        "acad6de1fc93436f5c0f1f4137751ef04f1aea3063e7036535970ffcfbd79f72"
    ),
    "fonts/ibm-plex-mono-regular.ttf": (
        "6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46"
    ),
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
@font-face{font-family:"Space Grotesk";src:url("assets/fonts/space-grotesk-variable.ttf") format("truetype");font-style:normal;font-weight:300 700;font-display:swap}
@font-face{font-family:"IBM Plex Mono";src:url("assets/fonts/ibm-plex-mono-regular.ttf") format("truetype");font-style:normal;font-weight:400;font-display:swap}
:root{--bg:#0b1111;--bg-deep:#080d0d;--surface:#171d1e;--surface-raised:#1b2223;--surface-soft:#111819;--text:#edf1ef;--muted:#a5aeaa;--dim:#89938f;--mint:#9ef6e5;--mint-bright:#58e4d0;--amber:#f3ce62;--border:rgba(158,246,229,.11);--border-strong:rgba(158,246,229,.25);--danger:#ff8d86;--focus:#f3ce62;font-family:"Space Grotesk",ui-sans-serif,system-ui,sans-serif;color:var(--text);background:var(--bg);color-scheme:dark}
*{box-sizing:border-box}html{max-width:100%;overflow-x:hidden;scroll-behavior:smooth}body{min-height:100vh;margin:0;max-width:100%;overflow-x:hidden;background-color:var(--bg);background-image:linear-gradient(var(--border) 1px,transparent 1px),linear-gradient(90deg,var(--border) 1px,transparent 1px);background-size:48px 48px;background-position:-1px -1px;color:var(--text)}body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:linear-gradient(180deg,rgba(8,13,13,.28),rgba(8,13,13,.9))}button,select,input{font:inherit;color:inherit}button,select,.format-option{min-height:44px}button{cursor:pointer}a{color:var(--mint)}a:hover{color:var(--mint-bright)}:focus-visible{outline:3px solid var(--focus);outline-offset:3px}.skip-link{position:absolute;left:12px;top:-80px;z-index:30;padding:10px 14px;border:1px solid var(--border-strong);background:var(--bg-deep);color:var(--text)}.skip-link:focus{top:12px}.shell{width:min(1280px,calc(100% - 40px));margin:0 auto;padding:30px 0 44px}.masthead{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:32px;align-items:end;padding:22px 0 24px;border-top:1px solid var(--border-strong);border-bottom:1px solid var(--border)}.eyebrow,.field-label,legend,.kpi-label,.effective,.meta-label{font-family:"IBM Plex Mono",ui-monospace,monospace;text-transform:uppercase;letter-spacing:.08em}.eyebrow{margin:0 0 10px;color:var(--mint-bright);font-size:.74rem}.masthead h1{max-width:850px;margin:0;font-size:clamp(2.25rem,6vw,5.1rem);font-weight:600;line-height:.92;letter-spacing:-.055em}.dek{max-width:760px;margin:18px 0 0;color:var(--muted);font-size:1.03rem;line-height:1.6}.meta-panel{min-width:270px;padding:14px 0 2px 20px;border-left:1px solid var(--border-strong);color:var(--muted);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.76rem;line-height:1.8}.meta-label{color:var(--dim);font-size:.66rem}.portfolio-link{display:inline-block;margin-top:10px}.gate-banner{display:flex;justify-content:space-between;gap:16px;align-items:center;margin:16px 0 12px;padding:12px 15px;border:1px solid var(--border-strong);background:var(--surface-soft);color:var(--mint);font-size:.9rem}.gate-banner.blocked{border-color:rgba(255,141,134,.45);color:var(--danger)}.toolbar{position:sticky;top:0;z-index:10;display:grid;grid-template-columns:minmax(280px,1fr) 180px auto;gap:14px;align-items:end;margin-bottom:12px;padding:14px;border:1px solid var(--border-strong);background:rgba(17,24,25,.97);backdrop-filter:blur(12px)}fieldset{min-width:0;margin:0;padding:0;border:0}legend,.field-label{display:block;margin:0 0 7px;color:var(--muted);font-size:.68rem}.format-options{display:grid;grid-template-columns:1fr 1fr;gap:8px}.format-option{position:relative;display:flex;align-items:center;justify-content:center;padding:8px 12px;border:1px solid var(--border);background:var(--surface);color:var(--muted);text-align:center;cursor:pointer}.format-option:has(input:checked){border-color:var(--format-color,var(--mint));background:var(--surface-raised);color:var(--text)}.format-option input{position:absolute;opacity:0;pointer-events:none}select{width:100%;padding:9px 36px 9px 11px;border:1px solid var(--border);border-radius:0;background:var(--surface);color:var(--text)}.toolbar-actions{display:flex;gap:8px;flex-wrap:wrap}.reset,.view-reset{padding:9px 13px;border:1px solid var(--border-strong);border-radius:0;background:transparent;color:var(--mint);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.72rem}.reset:hover,.view-reset:hover{background:var(--mint);color:var(--bg-deep)}.tabbar{display:flex;overflow-x:auto;border:1px solid var(--border);background:var(--bg-deep)}.tab{flex:1;padding:12px 14px;border:0;border-right:1px solid var(--border);border-radius:0;background:transparent;color:var(--muted);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.73rem;white-space:nowrap}.tab:last-child{border-right:0}.tab[aria-selected="true"]{background:var(--mint);color:var(--bg-deep)}.view{padding-top:20px}.section-head{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:14px}.section-head h2{margin:0;font-size:clamp(1.55rem,3vw,2.25rem);font-weight:550;letter-spacing:-.03em}.section-head p{margin:5px 0 0;color:var(--muted)}.effective{color:var(--dim);font-size:.68rem;text-align:right}.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:12px}.kpi,.card{border:1px solid var(--border);border-radius:0;background:var(--surface);box-shadow:none}.kpi{min-height:138px;padding:18px;position:relative}.kpi::before{content:"";position:absolute;top:-1px;left:-1px;width:38px;border-top:1px solid var(--mint)}.kpi-label{min-height:2.3em;margin:0;color:var(--dim);font-size:.66rem;line-height:1.45}.kpi-value{display:block;margin:11px 0 4px;color:var(--text);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:clamp(1.35rem,2.7vw,2.15rem);font-weight:400;letter-spacing:-.04em}.kpi-note{color:var(--muted);font-size:.77rem}.chart-grid{display:grid;grid-template-columns:1.25fr .75fr;gap:12px}.chart-grid.equal{grid-template-columns:1fr 1fr}.card{min-width:0;overflow:hidden}.card-head{display:flex;justify-content:space-between;gap:12px;align-items:start;padding:15px 16px 0}.card-head h3{margin:0;font-size:1rem;font-weight:600}.card-sub{margin:3px 0 0;color:var(--dim);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.67rem}.chart{position:relative;height:350px;min-width:0}.plot-surface{position:absolute;inset:0;width:100%;height:100%}.plot-surface.pending{visibility:hidden}.chart-fallback,.empty-chart{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;margin:0;padding:28px;color:var(--muted);text-align:center;line-height:1.55}.chart-fallback[hidden]{display:none}.chart.plot-failed{border-top:1px solid rgba(255,141,134,.28)}.chart.plot-failed .chart-fallback{color:var(--danger)}.data-summary{padding:10px 16px 14px;border-top:1px solid var(--border);color:var(--muted);font-size:.8rem}.data-summary summary{color:var(--mint);cursor:pointer}.summary-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 20px;padding-left:18px}.local-filter{max-width:430px;margin-bottom:12px;padding:14px}.notice{padding:12px 14px;border-left:2px solid var(--amber);background:var(--surface-soft);color:var(--muted)}.coverage{margin-top:0}.table-wrap{overflow-x:auto}.quality-table{width:100%;min-width:780px;border-collapse:collapse;font-size:.8rem}.quality-table caption{padding:14px 16px;color:var(--muted);text-align:left}.quality-table th,.quality-table td{padding:10px 12px;border-top:1px solid var(--border);text-align:left;vertical-align:top}.quality-table th{color:var(--dim);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.66rem;text-transform:uppercase;letter-spacing:.06em}.status-pass{color:var(--mint)}.status-fail{color:var(--danger)}.status-line{margin:14px 0 0;padding:10px 12px;border:1px solid var(--border);background:var(--surface-soft);color:var(--muted);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.72rem}.status-line.error{border-color:rgba(255,141,134,.4);color:var(--danger)}.site-footer{display:grid;grid-template-columns:1.4fr .6fr;gap:28px;margin-top:22px;padding-top:18px;border-top:1px solid var(--border-strong);color:var(--dim);font-size:.78rem;line-height:1.6}.site-footer p{margin:0}.modebar{top:5px!important;right:5px!important}.modebar-btn path{fill:var(--muted)!important}.modebar-btn:hover path,.modebar-btn.active path{fill:var(--mint)!important}
.plot-surface{position:static;inset:auto}.plot-surface.pending{visibility:visible}.chart-fallback{z-index:2;background:var(--surface)}body.mobile .shell{width:min(680px,calc(100% - 20px))}body.mobile .format-options,body.mobile .toolbar-actions{grid-template-columns:1fr!important}
body.mobile .shell{width:min(100% - 20px,680px);padding-top:14px}body.mobile .masthead,body.mobile .site-footer{grid-template-columns:1fr}body.mobile .masthead h1{font-size:2.35rem;overflow-wrap:anywhere}body.mobile .meta-panel{padding-left:0;border-left:0;border-top:1px solid var(--border);padding-top:14px}body.mobile .toolbar{position:static;grid-template-columns:1fr}body.mobile .format-options,body.mobile .toolbar-actions{display:grid;grid-template-columns:1fr 1fr}body.mobile .tabbar{display:grid;grid-template-columns:1fr 1fr;overflow:visible}body.mobile .tab{white-space:normal;border-bottom:1px solid var(--border)}body.mobile .kpis,body.mobile .chart-grid,body.mobile .chart-grid.equal{grid-template-columns:1fr}body.mobile .section-head{display:block}body.mobile .effective{text-align:left;margin-top:7px}body.mobile .chart{height:300px}body.mobile .summary-list{grid-template-columns:1fr}
@media(max-width:820px){.shell{width:min(100% - 20px,680px);padding-top:14px}.masthead,.site-footer{grid-template-columns:1fr}.masthead h1{font-size:clamp(2.2rem,11vw,3.6rem);overflow-wrap:anywhere}.meta-panel{padding-left:0;border-left:0;border-top:1px solid var(--border);padding-top:14px}.toolbar{position:static;grid-template-columns:1fr}.format-options,.toolbar-actions{display:grid;grid-template-columns:1fr 1fr}.tabbar{display:grid;grid-template-columns:1fr 1fr;overflow:visible}.tab{white-space:normal;border-bottom:1px solid var(--border)}.kpis,.chart-grid,.chart-grid.equal{grid-template-columns:1fr 1fr}.section-head{display:block}.effective{text-align:left;margin-top:7px}.summary-list{grid-template-columns:1fr}}
@media(max-width:560px){.format-options,.toolbar-actions,.kpis,.chart-grid,.chart-grid.equal{grid-template-columns:1fr}.chart{height:300px}.kpi{min-height:120px}.card-head{display:block}.card-sub{margin-top:6px}}
@media(max-width:360px){.shell{width:calc(100% - 16px)}.masthead h1{font-size:2rem}.kpi{padding:14px}.tab{padding-inline:8px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
"""


BODY = r"""
<a class="skip-link" href="#contenido">Saltar al contenido</a>
<div class="shell">
  <header class="masthead">
    <div><p class="eyebrow">Monitor mensual · Argentina</p><h1>Pulso del retail argentino</h1><p class="dek">Ventas reales, composición nominal y cobertura estadística para decidir sin mezclar universos de encuesta.</p></div>
    <div class="meta-panel" aria-label="Metadatos del tablero"><span class="meta-label">Corte</span><br><span id="meta-cutoff"></span><br><span class="meta-label">Extracción</span><br><span id="meta-snapshot"></span><br><span class="meta-label">Fuente</span><br>INDEC / Datos Argentina<br><a class="portfolio-link" href="https://alexanderhuth98.github.io/#proyectos">Volver a proyectos</a></div>
  </header>
  <div id="gate-banner" class="gate-banner" role="status"><span id="gate-copy"></span><strong id="gate-value"></strong></div>
  <form class="toolbar" aria-label="Filtros y acciones globales" onsubmit="return false">
    <fieldset><legend>Formato obligatorio</legend><div class="format-options">
      <label class="format-option" style="--format-color:#9ef6e5"><input type="radio" name="retail-format" value="supermarkets" checked>Supermercados</label>
      <label class="format-option" style="--format-color:#f3ce62"><input type="radio" name="retail-format" value="wholesale">Autoservicios mayoristas</label>
    </div></fieldset>
    <label><span class="field-label">Período / año</span><select id="year-filter" aria-label="Seleccionar período"></select></label>
    <div class="toolbar-actions"><button id="reset-filters" class="reset" type="button">Restablecer filtros</button><button id="reset-charts" class="view-reset" type="button" aria-controls="contenido">Restablecer vista</button></div>
  </form>
  <nav class="tabbar" aria-label="Vistas del tablero" role="tablist">
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
        <article class="kpi"><p class="kpi-label">Variación real mensual desestacionalizada</p><strong class="kpi-value" id="real-mom">—</strong><small class="kpi-note">% vs. mes anterior</small></article>
        <article class="kpi"><p class="kpi-label">Ventas nominales</p><strong class="kpi-value" id="nominal-sales">—</strong><small class="kpi-note">millones de ARS corrientes</small></article>
      </div>
      <div class="chart-grid"><article class="card"><div class="card-head"><div><h3>Actividad real</h3><p class="card-sub">Índice original y tendencia-ciclo · base 2017 = 100</p></div></div><div id="overview-index-chart" class="chart" role="img" aria-label="Evolución del índice real original y tendencia"><p class="chart-fallback">No se pudo mostrar este gráfico. Los valores principales permanecen disponibles en las tarjetas.</p></div><details class="data-summary"><summary>Resumen accesible del gráfico</summary><ul id="overview-index-summary" class="summary-list"></ul></details></article>
      <article class="card"><div class="card-head"><div><h3>Facturación nominal</h3><p class="card-sub">Millones de ARS corrientes · eje separado</p></div></div><div id="overview-sales-chart" class="chart" role="img" aria-label="Evolución de ventas nominales"><p class="chart-fallback">No se pudo mostrar este gráfico. Consultá la tarjeta de ventas nominales.</p></div><details class="data-summary"><summary>Resumen accesible del gráfico</summary><ul id="overview-sales-summary" class="summary-list"></ul></details></article></div>
    </section>
    <section id="payments" class="view" role="tabpanel" aria-labelledby="tab-payments" hidden>
      <header class="section-head"><div><h2>Medios de pago</h2><p>Participación dentro del formato seleccionado; los cambios se expresan en puntos porcentuales.</p></div><div class="effective" id="payments-date"></div></header>
      <div id="payment-kpis" class="kpis"></div>
      <div class="chart-grid"><article class="card"><div class="card-head"><div><h3>Evolución de la composición</h3><p class="card-sub">Participación mensual (%)</p></div></div><div id="payments-line-chart" class="chart" role="img" aria-label="Evolución de la participación por medio de pago"><p class="chart-fallback">No se pudo mostrar este gráfico. Consultá las participaciones actuales.</p></div><details class="data-summary"><summary>Resumen accesible del último mes</summary><ul id="payments-summary" class="summary-list"></ul></details></article><article class="card"><div class="card-head"><div><h3>Cambio interanual</h3><p class="card-sub">Puntos porcentuales (pp)</p></div></div><div id="payments-delta-chart" class="chart" role="img" aria-label="Cambio interanual de participación por medio de pago"><p class="chart-fallback">No se pudo mostrar este gráfico. Los cambios figuran en las tarjetas.</p></div></article></div>
    </section>
    <section id="categories" class="view" role="tabpanel" aria-labelledby="tab-categories" hidden>
      <header class="section-head"><div><h2>Categorías</h2><p>Evolución nominal y participación dentro de cada formato.</p></div><div class="effective" id="categories-date"></div></header>
      <div class="card local-filter"><label><span class="field-label">Categoría destacada</span><select id="category-filter"></select></label></div>
      <p class="notice"><strong>Lectura responsable:</strong> la variación nominal por categoría no equivale a volumen ni descuenta inflación.</p>
      <div class="kpis">
        <article class="kpi"><p class="kpi-label">Ventas nominales · categoría</p><strong class="kpi-value" id="category-sales">—</strong><small class="kpi-note">millones de ARS corrientes</small></article>
        <article class="kpi"><p class="kpi-label">Participación de categoría</p><strong class="kpi-value" id="category-share">—</strong><small class="kpi-note">% dentro del formato</small></article>
        <article class="kpi"><p class="kpi-label">Variación nominal interanual</p><strong class="kpi-value" id="category-yoy">—</strong><small class="kpi-note">% nominal</small></article>
        <article class="kpi"><p class="kpi-label">Fecha efectiva</p><strong class="kpi-value" id="category-date">—</strong><small class="kpi-note">último mes observado</small></article>
      </div>
      <div class="chart-grid equal"><article class="card"><div class="card-head"><div><h3>Evolución de la composición</h3><p class="card-sub">Participación mensual (%) · la categoría elegida se destaca</p></div></div><div id="categories-mix-chart" class="chart" role="img" aria-label="Evolución de la composición de categorías"><p class="chart-fallback">No se pudo mostrar este gráfico. Consultá la clasificación del último mes.</p></div></article><article class="card"><div class="card-head"><div><h3>Clasificación del último mes</h3><p class="card-sub">Participación (%)</p></div></div><div id="categories-ranking-chart" class="chart" role="img" aria-label="Clasificación de categorías del último mes"><p class="chart-fallback">No se pudo mostrar este gráfico. Consultá el resumen accesible.</p></div><details class="data-summary"><summary>Clasificación en texto</summary><ol id="categories-summary"></ol></details></article></div>
    </section>
    <section id="channels" class="view" role="tabpanel" aria-labelledby="tab-channels" hidden>
      <header class="section-head"><div><h2>Canales y calidad</h2><p>Cobertura observada, composición en línea/salón y controles previos a publicación.</p></div><div class="effective" id="channels-period"></div></header>
      <div class="kpis">
        <article class="kpi"><p class="kpi-label">Participación en línea</p><strong class="kpi-value" id="online-share">—</strong><small class="kpi-note" id="online-note">% observado</small></article>
        <article class="kpi"><p class="kpi-label">Última fecha observada</p><strong class="kpi-value" id="channel-date">—</strong><small class="kpi-note">detalle de canal</small></article>
        <article class="kpi"><p class="kpi-label">Fallas de severidad alta</p><strong class="kpi-value" id="high-fails">—</strong><small class="kpi-note">controles bloqueantes</small></article>
        <article class="kpi"><p class="kpi-label">Estado de publicación</p><strong class="kpi-value" id="quality-gate">—</strong><small class="kpi-note">requiere al menos un control alto y ninguna falla</small></article>
      </div>
      <p id="channel-coverage" class="notice coverage"></p>
      <article class="card"><div class="card-head"><div><h3>Canal en línea / salón</h3><p class="card-sub">Participación mensual (%) · los faltantes no se imputan como cero</p></div></div><div id="channels-chart" class="chart" role="img" aria-label="Evolución de participación en línea y salón"><p class="chart-fallback">No se pudo mostrar este gráfico. Consultá la fecha efectiva y la nota de cobertura.</p></div><details class="data-summary"><summary>Resumen accesible</summary><ul id="channels-summary" class="summary-list"></ul></details></article>
      <article class="card" style="margin-top:12px"><div class="table-wrap"><table class="quality-table"><caption>Los 11 controles del corte publicado</caption><thead><tr><th scope="col">Fuente</th><th scope="col">Severidad</th><th scope="col">Estado</th><th scope="col">Control</th><th scope="col">Detalle</th></tr></thead><tbody id="quality-body"></tbody></table></div></article>
    </section>
  </main>
  <p id="app-status" class="status-line" role="status" aria-live="polite">Cargando visualizaciones…</p>
  <footer class="site-footer"><p><strong>Contexto:</strong> supermercados y autoservicios mayoristas son universos distintos; nunca se suman. 2026 es parcial. El canal mayorista posterior a agosto de 2022 es no observado, no cero.</p><p>Fuente: INDEC / Datos Argentina · Datos: CC BY 4.0 · Código: MIT.</p></footer>
</div>
"""


JS = r"""
(()=>{'use strict';
let DATA;
let renderTasks=[];
let renderCycle=0;
const $=id=>document.getElementById(id);
const LABELS={supermarkets:'Supermercados',wholesale:'Autoservicios mayoristas',cash:'Efectivo',debit_card:'Tarjeta de débito',credit_card:'Tarjeta de crédito',other:'Otros',beverages:'Bebidas',grocery:'Almacén',bakery:'Panadería',dairy:'Lácteos',meat:'Carnes',fruit_and_vegetables:'Verdulería y frutería',prepared_food:'Alimentos preparados / rotisería',cleaning_and_personal_care:'Limpieza y perfumería',clothing_and_home_textiles:'Indumentaria y textiles',electronics_and_home:'Electrónicos y hogar',online:'En línea',showroom:'Salón'};
const CHECK_LABELS={headline_scale_reconciles:'La escala del total reconcilia',payment_components_reconcile:'Los medios de pago reconcilian',food_components_reconcile:'Las categorías de alimentos reconcilian',nominal_totals_agree:'Los totales nominales coinciden',observed_channel_components_reconcile:'Los canales observados reconcilian',wholesale_channel_gap_preserved:'Se preserva el faltante de canal mayorista'};
const DETAIL_LABELS={headline_scale_reconciles:'El total a precios corrientes en millones reconcilia con el detalle en miles.',payment_components_reconcile:'Los componentes por medio de pago reconcilian con su total.',food_components_reconcile:'Las categorías de alimentos reconcilian con su subtotal.',nominal_totals_agree:'Los totales por canal, medio de pago y categoría coinciden.',observed_channel_components_reconcile:'Los canales observados reconcilian; se excluyen los meses no disponibles.',wholesale_channel_gap_preserved:'El detalle de canal mayorista permanece no disponible desde septiembre de 2022.'};
const COLORS={supermarkets:'#9ef6e5',wholesale:'#f3ce62',cash:'#9ef6e5',debit_card:'#58e4d0',credit_card:'#f3ce62',other:'#a5aeaa',online:'#58e4d0',showroom:'#f3ce62'};
const PLOT_CONFIG=Object.freeze({responsive:true,displayModeBar:true,displaylogo:false,scrollZoom:false,doubleClick:'reset+autosize',locale:'es',modeBarButtonsToRemove:['toImage','sendDataToCloud','select2d','lasso2d','toggleSpikelines','hoverClosestCartesian','hoverCompareCartesian']});
const state={format:'supermarkets',year:'',category:'grocery',view:'overview'};
const valid=value=>value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value));
const fmt=(value,digits=1)=>valid(value)?new Intl.NumberFormat('es-AR',{minimumFractionDigits:digits,maximumFractionDigits:digits}).format(Number(value)):'No disponible';
const signed=(value,unit)=>valid(value)?`${Number(value)>0?'+':''}${fmt(value,1)}${unit}`:'No disponible';
const month=value=>value?new Intl.DateTimeFormat('es-AR',{month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(`${value}T00:00:00`)):'No disponible';
const periodRows=rows=>rows.filter(row=>row.retail_format===state.format&&(state.year==='all'||row.month.startsWith(state.year)));
const latestDate=rows=>rows.length?rows.reduce((a,b)=>a.month>b.month?a:b).month:null;
const setText=(id,value)=>{$(id).textContent=value};
const latestRows=rows=>{const date=latestDate(rows);return rows.filter(row=>row.month===date)};
function layout(ytitle,extra={}){const base={paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{family:'IBM Plex Mono, monospace',color:'#a5aeaa',size:11},margin:{l:58,r:20,t:26,b:54},xaxis:{gridcolor:'rgba(158,246,229,.11)',linecolor:'rgba(158,246,229,.25)',tickformat:'%b\n%Y',dtick:state.year==='all'?'M12':'M1',fixedrange:false,automargin:true},yaxis:{title:ytitle,gridcolor:'rgba(158,246,229,.11)',linecolor:'rgba(158,246,229,.25)',zerolinecolor:'rgba(158,246,229,.25)',fixedrange:false,automargin:true},legend:{orientation:'h',y:-.22},hoverlabel:{bgcolor:'#1b2223',bordercolor:'#58e4d0',font:{color:'#edf1ef'}}};return{...base,...extra,xaxis:{...base.xaxis,...(extra.xaxis||{})},yaxis:{...base.yaxis,...(extra.yaxis||{})}}}
function fallbackFor(node){let fallback=node.querySelector('.chart-fallback');if(!fallback){fallback=Object.assign(document.createElement('p'),{className:'chart-fallback',textContent:'No se pudo mostrar este gráfico. Los datos y filtros siguen disponibles.'});node.prepend(fallback)}return fallback}
function purgeSurface(surface){if(window.Plotly&&typeof window.Plotly.purge==='function'){try{window.Plotly.purge(surface)}catch(error){console.error('No se pudo liberar una visualización.',error)}}surface.remove()}
function plotFailure(node,surface,error){if(surface&&surface.isConnected)purgeSurface(surface);node.querySelectorAll('.plot-surface').forEach(purgeSurface);const fallback=fallbackFor(node);fallback.hidden=false;node.classList.add('plot-failed');console.error(`No se pudo renderizar ${node.id}.`,error);return false}
function plot(id,traces,chartLayout){const node=$(id);const fallback=fallbackFor(node);const generation=(node.plotGeneration||0)+1;node.plotGeneration=generation;if(!window.Plotly||typeof window.Plotly.react!=='function'){const task=Promise.resolve(plotFailure(node,null,new Error('Plotly no está disponible.')));renderTasks.push(task);return task}const surface=document.createElement('div');surface.className='plot-surface pending';surface.setAttribute('aria-hidden','true');node.append(surface);let result;try{result=window.Plotly.react(surface,traces,chartLayout,PLOT_CONFIG)}catch(error){const task=Promise.resolve(plotFailure(node,surface,error));renderTasks.push(task);return task}const task=Promise.resolve(result).then(()=>{if(node.plotGeneration!==generation){purgeSurface(surface);return true}node.querySelectorAll('.plot-surface').forEach(previous=>{if(previous!==surface)purgeSurface(previous)});surface.classList.remove('pending');surface.removeAttribute('aria-hidden');fallback.hidden=true;node.classList.remove('plot-failed');return true}).catch(error=>plotFailure(node,surface,error));renderTasks.push(task);return task}
function emptyChart(id,message){const node=$(id);node.plotGeneration=(node.plotGeneration||0)+1;node.querySelectorAll('.plot-surface').forEach(purgeSurface);node.replaceChildren(Object.assign(document.createElement('p'),{className:'empty-chart',textContent:message}));node.classList.remove('plot-failed')}
function list(id,items){const node=$(id);node.replaceChildren(...items.map(text=>Object.assign(document.createElement('li'),{textContent:text})))}
function renderOverview(){const rows=periodRows(DATA.monthly_summary);const current=latestRows(rows)[0];setText('overview-date',current?`Fecha efectiva: ${month(current.month)}`:'Sin observaciones para el período');setText('real-index',current?fmt(current.real_sales_index_original,1):'No observado');setText('real-yoy',current?signed(current.real_sales_yoy_pct,'%'):'No observado');setText('real-mom',current?signed(current.real_sales_sa_mom_pct,'%'):'No observado');setText('nominal-sales',current?fmt(current.nominal_sales_million_ars,0):'No observado');if(!rows.length){emptyChart('overview-index-chart','Sin datos para la selección.');emptyChart('overview-sales-chart','Sin datos para la selección.');return}const color=COLORS[state.format];plot('overview-index-chart',[{x:rows.map(r=>r.month),y:rows.map(r=>r.real_sales_index_original),name:'Original',type:'scatter',mode:'lines',line:{color,width:3}},{x:rows.map(r=>r.month),y:rows.map(r=>r.real_sales_index_trend),name:'Tendencia-ciclo',type:'scatter',mode:'lines',line:{color:'#f3ce62',width:2,dash:'dot'}}],layout('Índice base 2017 = 100'));plot('overview-sales-chart',[{x:rows.map(r=>r.month),y:rows.map(r=>r.nominal_sales_million_ars),name:'Ventas',type:'bar',marker:{color}}],layout('Millones de ARS',{showlegend:false}));list('overview-index-summary',[`Inicio: ${month(rows[0].month)}, índice ${fmt(rows[0].real_sales_index_original,1)}.`,`Último: ${month(current.month)}, índice ${fmt(current.real_sales_index_original,1)}.`,`Tendencia del último mes: ${fmt(current.real_sales_index_trend,1)}.`]);list('overview-sales-summary',[`Último mes: ${month(current.month)}.`,`Ventas nominales: ${fmt(current.nominal_sales_million_ars,0)} millones de ARS.`])}
function renderPayments(){const rows=periodRows(DATA.payment_mix).filter(r=>r.is_observed);const current=latestRows(rows);const date=latestDate(rows);setText('payments-date',date?`Fecha efectiva: ${month(date)}`:'Sin observaciones');const methods=['cash','debit_card','credit_card','other'];const cards=methods.map(method=>{const row=current.find(r=>r.payment_method===method);const article=document.createElement('article');article.className='kpi';const label=document.createElement('p');label.className='kpi-label';label.textContent=LABELS[method];const value=document.createElement('strong');value.className='kpi-value';value.textContent=row?`${fmt(row.share_pct,1)}%`:'No observado';const note=document.createElement('small');note.className='kpi-note';note.textContent=row&&Number.isFinite(Number(row.share_yoy_pp))?`${signed(row.share_yoy_pp,' pp')} interanual`:'Sin comparación interanual';article.append(label,value,note);return article});$('payment-kpis').replaceChildren(...cards);if(!rows.length){emptyChart('payments-line-chart','Sin observaciones para el período.');emptyChart('payments-delta-chart','Sin comparación disponible.');list('payments-summary',['Sin observaciones para la selección.']);return}plot('payments-line-chart',methods.map(method=>({x:rows.filter(r=>r.payment_method===method).map(r=>r.month),y:rows.filter(r=>r.payment_method===method).map(r=>r.share_pct),name:LABELS[method],type:'scatter',mode:'lines',line:{color:COLORS[method],width:2.5}})),layout('Participación (%)'));const deltas=methods.map(method=>current.find(r=>r.payment_method===method)?.share_yoy_pp??null);plot('payments-delta-chart',[{x:methods.map(m=>LABELS[m]),y:deltas,type:'bar',marker:{color:deltas.map(v=>v!==null&&v<0?'#a5aeaa':'#58e4d0')}}],layout('Cambio (pp)',{showlegend:false,xaxis:{tickangle:-18}}));list('payments-summary',current.map(row=>`${LABELS[row.payment_method]}: ${fmt(row.share_pct,1)}%; cambio ${signed(row.share_yoy_pp,' pp')}.`))}
function renderCategories(){const allFormat=DATA.category_mix.filter(r=>r.retail_format===state.format&&r.is_observed);const available=[...new Set(allFormat.map(r=>r.category))];if(!available.includes(state.category))state.category=available[0];const select=$('category-filter');select.replaceChildren(...available.map(category=>{const option=document.createElement('option');option.value=category;option.textContent=LABELS[category]||category;option.selected=category===state.category;return option}));const rows=periodRows(DATA.category_mix).filter(r=>r.is_observed);const date=latestDate(rows);const current=rows.find(r=>r.month===date&&r.category===state.category);setText('categories-date',date?`Fecha efectiva: ${month(date)}`:'Sin observaciones');setText('category-sales',current?fmt(current.sales_thousand_ars/1000,0):'No observado');setText('category-share',current?`${fmt(current.share_pct,1)}%`:'No observado');setText('category-yoy',current?signed(current.nominal_sales_yoy_pct,'%'):'No disponible');setText('category-date',current?month(current.month):'No observado');if(!rows.length){emptyChart('categories-mix-chart','Sin observaciones para el período.');emptyChart('categories-ranking-chart','Sin clasificación para el período.');list('categories-summary',['Sin observaciones para la selección.']);return}const categories=[...new Set(rows.map(r=>r.category))];plot('categories-mix-chart',categories.map(category=>{const series=rows.filter(r=>r.category===category);const selected=category===state.category;return{x:series.map(r=>r.month),y:series.map(r=>r.share_pct),name:LABELS[category]||category,type:'scatter',mode:'lines',opacity:selected?1:.35,line:{color:selected?COLORS[state.format]:'#89938f',width:selected?4:1.4}}}),layout('Participación (%)'));const ranking=latestRows(rows).sort((a,b)=>a.share_pct-b.share_pct);plot('categories-ranking-chart',[{x:ranking.map(r=>r.share_pct),y:ranking.map(r=>LABELS[r.category]||r.category),type:'bar',orientation:'h',marker:{color:ranking.map(r=>r.category===state.category?COLORS[state.format]:'#89938f')}}],layout('Participación (%)',{showlegend:false,margin:{l:145,r:20,t:26,b:48},xaxis:{tickformat:'.1f'},yaxis:{title:''}}));list('categories-summary',[...ranking].reverse().map(r=>`${LABELS[r.category]||r.category}: ${fmt(r.share_pct,1)}%.`))}
function renderChannels(){const formatRows=DATA.channel_mix.filter(r=>r.retail_format===state.format);const rows=periodRows(DATA.channel_mix);const observedToPeriod=formatRows.filter(r=>r.is_observed&&(state.year==='all'||Number(r.month.slice(0,4))<=Number(state.year)));const lastObserved=latestDate(observedToPeriod);const current=formatRows.find(r=>r.month===lastObserved&&r.channel==='online'&&r.is_observed);setText('online-share',current?`${fmt(current.share_pct,2)}%`:'No observado');setText('online-note',current?`% observado en ${month(current.month)}`:'sin imputar cero');setText('channel-date',month(lastObserved));setText('channels-period',state.year==='all'?'Todo el período':`Período ${state.year}`);const highs=DATA.quality_checks.filter(r=>String(r.severity).toUpperCase()==='HIGH');const failures=highs.filter(r=>String(r.status).toUpperCase()!=='PASS').length;setText('high-fails',String(failures));setText('quality-gate',DATA.metadata.gate==='PASS'?'APROBADO':'BLOQUEADO');const coverage=state.format==='wholesale'?'Mayoristas: el detalle en línea/salón termina en agosto de 2022. Desde septiembre de 2022 se muestra como no observado, nunca como cero.':'Supermercados: detalle en línea/salón observado hasta el último mes del corte.';setText('channel-coverage',coverage);const observedRows=rows.filter(r=>r.is_observed);if(!observedRows.length){emptyChart('channels-chart','No observado en este período. Último dato mayorista: agosto de 2022.');list('channels-summary',[coverage])}else{const channels=['showroom','online'];plot('channels-chart',channels.map(channel=>{const series=rows.filter(r=>r.channel===channel);return{x:series.map(r=>r.month),y:series.map(r=>r.is_observed?r.share_pct:null),connectgaps:false,name:LABELS[channel],type:'scatter',mode:'lines',line:{color:COLORS[channel],width:2.5}}}),layout('Participación (%)'));const currentObserved=latestRows(observedRows);list('channels-summary',currentObserved.map(r=>`${LABELS[r.channel]}: ${fmt(r.share_pct,2)}% en ${month(r.month)}.`))}}
function renderQuality(){const body=$('quality-body');const rows=DATA.quality_checks.map(check=>{const tr=document.createElement('tr');const status=String(check.status).toUpperCase()==='PASS'?'Aprobado':'Con falla';const severity=String(check.severity).toUpperCase()==='HIGH'?'Alta':check.severity;const values=[LABELS[check.source]||check.source,severity,status,CHECK_LABELS[check.check]||check.check,DETAIL_LABELS[check.check]||check.detail];values.forEach((value,index)=>{const td=document.createElement('td');td.textContent=value;if(index===2)td.className=status==='Aprobado'?'status-pass':'status-fail';tr.append(td)});return tr});body.replaceChildren(...rows)}
function update(){const cycle=++renderCycle;renderTasks=[];document.documentElement.style.setProperty('--format-color',COLORS[state.format]);renderOverview();renderPayments();renderCategories();renderChannels();renderQuality();const tasks=[...renderTasks];Promise.all(tasks).then(results=>{if(cycle!==renderCycle)return;const failures=results.filter(result=>!result).length;if(failures){$('app-status').className='status-line error';setText('app-status',`Datos listos: ${LABELS[state.format]}. ${failures} visualizaciones no pudieron cargarse; los indicadores y resúmenes siguen disponibles.`)}else{$('app-status').className='status-line';setText('app-status',`Datos listos: ${LABELS[state.format]}, ${state.year==='all'?'todo el período':state.year}.`)}})}
function showView(view,focus=false){state.view=view;document.querySelectorAll('.tab').forEach(tab=>{const selected=tab.dataset.view===view;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;if(selected&&focus)tab.focus()});document.querySelectorAll('.view').forEach(section=>section.hidden=section.id!==view);update()}
function resetChartViews(){const plots=[...document.querySelectorAll('.plot-surface.js-plotly-plot')];if(!window.Plotly||typeof window.Plotly.relayout!=='function'||!plots.length){$('app-status').className='status-line error';setText('app-status','No hay gráficos disponibles para restablecer. Los indicadores y resúmenes siguen accesibles.');return}const tasks=plots.map(node=>{try{return Promise.resolve(window.Plotly.relayout(node,{'xaxis.autorange':true,'yaxis.autorange':true}))}catch(error){console.error('No se pudo restablecer una visualización.',error);return Promise.reject(error)}});Promise.allSettled(tasks).then(results=>{const failures=results.filter(result=>result.status==='rejected').length;$('app-status').className=failures?'status-line error':'status-line';setText('app-status',failures?'Algunas visualizaciones no pudieron restablecerse.':'Vista de los gráficos restablecida.')})}
function init(){state.year=String(DATA.metadata.years.at(-1));setText('meta-cutoff',month(DATA.metadata.latest_month));setText('meta-snapshot',DATA.metadata.snapshot_date==='No disponible'?DATA.metadata.snapshot_date:new Intl.DateTimeFormat('es-AR',{dateStyle:'medium',timeZone:'UTC'}).format(new Date(`${DATA.metadata.snapshot_date}T00:00:00`)));const pass=DATA.metadata.gate==='PASS';$('gate-banner').classList.toggle('blocked',!pass);setText('gate-copy',pass?'Controles de severidad alta completos: resultados aptos para publicación.':'Publicación bloqueada: resultados exploratorios, no publicables.');setText('gate-value',pass?'APROBADO':'BLOQUEADO');const year=$('year-filter');const all=document.createElement('option');all.value='all';all.textContent='Todo el período';year.append(all,...DATA.metadata.years.map(value=>{const option=document.createElement('option');option.value=String(value);option.textContent=value===2026?'2026 · parcial':String(value);option.selected=String(value)===state.year;return option}));document.querySelectorAll('input[name="retail-format"]').forEach(input=>input.addEventListener('change',event=>{state.format=event.target.value;update()}));year.addEventListener('change',event=>{state.year=event.target.value;update()});$('category-filter').addEventListener('change',event=>{state.category=event.target.value;update()});$('reset-filters').addEventListener('click',()=>{state.format='supermarkets';state.year=String(DATA.metadata.years.at(-1));state.category='grocery';document.querySelector('input[value="supermarkets"]').checked=true;year.value=state.year;showView('overview')});$('reset-charts').addEventListener('click',resetChartViews);document.querySelectorAll('.tab').forEach(tab=>{tab.addEventListener('click',()=>showView(tab.dataset.view));tab.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();const tabs=[...document.querySelectorAll('.tab')];const next=(tabs.indexOf(tab)+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;showView(tabs[next].dataset.view,true)})});update()}
window.addEventListener('DOMContentLoaded',()=>{try{DATA=JSON.parse(document.getElementById('dashboard-data').textContent);init()}catch(error){$('app-status').className='status-line error';setText('app-status','No se pudo iniciar el tablero. Los datos no se presentan como publicables.');console.error(error)}});
})();
"""


def render_dashboard(payload: dict[str, Any], *, mobile: bool = False) -> str:
    """Render one offline-capable HTML variant backed by versioned local assets."""
    body_class = "mobile" if mobile else "desktop"
    variant = "móvil" if mobile else "escritorio"
    return f"""<!doctype html>
<html lang="es-AR" data-variant="{variant}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Tablero de ventas reales, pagos, categorías, canales y calidad del retail argentino.">
  <title>Pulso del retail argentino · {variant.capitalize()}</title>
  <style>{CSS}</style>
  <script src="assets/plotly-basic-2.35.2.min.js" defer></script>
  <script src="assets/plotly-locale-es-2.35.2.js" defer></script>
</head>
<body class="{body_class}">
{BODY}
<script id="dashboard-data" type="application/json">{_safe_json(payload)}</script>
<script>{JS}</script>
</body>
</html>
"""


def _copy_dashboard_assets(site_dir: Path) -> None:
    """Verify pinned dashboard assets before copying them into the static site."""
    for relative_path, expected_hash in ASSET_HASHES.items():
        source = ASSET_SOURCE_DIR / relative_path
        if not source.is_file():
            raise DashboardContractError(f"Falta el asset local del dashboard: {relative_path}")
        actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise DashboardContractError(
                f"Integridad inválida para {relative_path}: {actual_hash} != {expected_hash}"
            )
        target = site_dir / "assets" / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def export_dashboard(
    data_dir: Path = config.PORTFOLIO_DATA_DIR,
    site_dir: Path = config.SITE_DIR,
) -> tuple[Path, Path]:
    """Generate both responsive entry points and their verified local assets."""
    site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)
    manifest = config.MANIFEST_DIR / "raw_sources.jsonl"
    payload = build_dashboard_payload(data_dir, manifest if manifest.exists() else None)
    if payload["metadata"]["gate"] != "PASS":
        raise DashboardContractError("Gate HIGH bloqueado: no se genera el sitio publicable")
    _copy_dashboard_assets(site_dir)
    desktop = site_dir / "index.html"
    mobile = site_dir / "mobile.html"
    desktop.write_text(render_dashboard(payload), encoding="utf-8")
    mobile.write_text(render_dashboard(payload, mobile=True), encoding="utf-8")
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")
    (site_dir / "README.md").write_text(
        "# Sitio estático generado\n\n"
        "No edite `index.html`, `mobile.html` ni `assets/` manualmente. Regenerar desde los "
        "cinco CSV curados con:\n\n```powershell\nargentina-retail-sales export\n```\n\n"
        "Plotly Basic 2.35.2 y las fuentes locales se copian desde el paquete y se validan "
        "contra los SHA-256 declarados en `dashboard.py`.\n",
        encoding="utf-8",
    )
    return desktop, mobile
