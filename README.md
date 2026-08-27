# Pulso del retail argentino

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/alexanderhuth98/argentina-retail-sales/actions/workflows/ci.yml/badge.svg)](https://github.com/alexanderhuth98/argentina-retail-sales/actions/workflows/ci.yml)

Caso reproducible de Data Analytics sobre ventas mensuales de supermercados y
autoservicios mayoristas de Argentina. Separa crecimiento nominal de evolucion real y
explica cambios en pagos, categorias y canales desde 2017 con Python, SQL Server y Power BI.

El PBIX esta publicado como activo de GitHub Release. No hay publicacion en Power BI
Service; la actualizacion/render final requiere Power BI Desktop y una instancia SQL Server.

## Impacto en 60 segundos

**Ultimo mes observado: mayo de 2026; 2026 es un ano parcial.**

| Area | Supermercados | Autoservicios mayoristas |
|---|---:|---:|
| Indice real original, base 2017=100 | `80,5` | `80,6` |
| Variacion real interanual | `-0,7%` | `-2,3%` |
| Variacion real mensual desestacionalizada | `+0,9%` | `+2,3%` |
| Variacion nominal interanual | `+25,9%` | `+23,7%` |

El crecimiento nominal no implico crecimiento real en mayo de 2026. En supermercados,
credito represento `45,0%` y efectivo `16,5%`; en mayoristas, otros medios representaron
`32,3%`. Almacen fue la principal categoria nominal en ambos formatos (`27,1%` y `44,4%`).
El canal online de supermercados alcanzo `3,43%`; el ultimo dato mayorista sigue siendo
agosto de 2022 (`0,03%`). Los `11` controles `HIGH` publicados estan en `PASS`.

## Preguntas de negocio

1. Las ventas reales se recuperan o el crecimiento observado es principalmente nominal?
2. Como cambio el uso de efectivo, debito, credito y otros medios de pago?
3. Que categorias ganaron o perdieron participacion dentro de cada formato?
4. El canal online de supermercados mantuvo el salto de 2020?
5. Que cobertura y controles deben verse antes de usar un resultado?

## Alcance defendible

- Los formatos son universos de encuesta distintos: se comparan tasas, indices y shares,
  pero no se suman como un mercado unico.
- El detalle por categoria, pago y canal esta en miles de ARS corrientes; no mide volumen.
- Los indices reales usan la base propia 2017=100.
- El detalle de canal mayorista termina en agosto de 2022. Los meses siguientes son nulos
  estructurales, no ceros.
- Las tendencias son descriptivas; no demuestran causalidad ni sustitucion de clientes.

## Solucion

- Descarga dos CSV oficiales con escritura temporal, SHA-256 y manifiesto.
- Valida contrato, fechas mensuales continuas, no negatividad y reconciliaciones.
- Publica cinco CSV agregados: `5` tablas, `3.966` filas y `11` controles `HIGH/PASS`.
- Despliega una capa SQL Server tipada con claves, checks, indices y carga atomica.
- Bloquea la publicacion SQL si falta un control `HIGH` o alguno no esta en `PASS`.
- Modela cinco hechos, calendario y cuatro dimensiones conformadas en Power BI.
- Devuelve `BLANK` en KPIs cuando se seleccionan ambos formatos.
- Versiona cuatro paginas PBIR y valida sus fuentes, tipos, relaciones y referencias.

## Arquitectura

```text
Datos Argentina / INDEC -> CSV raw + SHA-256 -> pandas -> contratos y reconciliacion
    -> cinco CSV de portfolio -> staging SQL Server -> gate HIGH -> retail.*
    -> vistas y medidas -> modelo semantico PBIP -> cuatro paginas Power BI
```

La carga SQL reemplaza las cinco tablas dentro de una unica transaccion. Una falla hace
rollback y conserva la ultima publicacion valida. No se versionan credenciales, rutas
personales, caches ni PBIX.

## Stack

`Python 3.11` | `pandas` | `SQL Server` | `T-SQL` | `Power BI PBIP` | `pytest` | `Ruff`

## Explorar

| Recurso | Contenido |
|---|---|
| [Caso de estudio ES](reports/case_study_es.md) | Narrativa ejecutiva, hallazgos y recomendaciones. |
| [Case study EN](reports/case_study_en.md) | English executive report. |
| [Dashboard spec](docs/dashboard_spec.md) | Objetivo, audiencia, KPIs, filtros, layout e interacciones. |
| [Metodologia](docs/methodology.md) | Unidades, comparaciones y faltantes. |
| [Arquitectura](docs/architecture.md) | Flujo, granos y controles. |
| [Diccionario](docs/data_dictionary.md) | Contrato de los cinco datasets. |
| [Operaciones](docs/operations.md) | Pipeline, SQL Server, Power BI y recuperacion. |
| [Releases](docs/releases.md) | Empaquetado de PBIX y hashes como activos de GitHub Release. |
| [SQL highlights](docs/sql_highlights.md) | Patrones T-SQL centrales. |
| [Power BI](powerbi/README.md) | Modelo, paginas, conexion y validacion. |
| [English README](README_EN.md) | Concise English project overview. |

## Ejecutar

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\argentina-retail-sales.exe all
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest --cov=argentina_retail_sales --cov-report=term-missing
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\powerbi\validate_pbip.ps1 -SkipTom
```

La capa SQL se despliega con `sqlcmd -i .\sql\deploy.sql`; consulte
[`sql/README.md`](sql/README.md) antes de cargar. La CI de GitHub y GitLab ejecuta lint,
tests, cobertura y validacion estructural PBIP.

## Fuente y licencias

Datos oficiales mensuales publicados en Datos Argentina con fuente INDEC y licencia
`CC BY 4.0`. El snapshot recuperado el `2026-08-27` cubre enero de 2017 a mayo de 2026;
los hashes estan en `manifests/raw_sources.jsonl`. Codigo y documentacion: MIT. MIT no
relicencia los datos; revise `DATA_LICENSE.md` antes de redistribuirlos.
