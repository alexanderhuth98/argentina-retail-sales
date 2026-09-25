# Operaciones

## Requisitos

- Python `>=3.11,<3.13`.
- SQL Server 2017+ y `sqlcmd` para la capa de servicio.
- Power BI Desktop para refresco, render y layout movil; no para el pipeline Python.

## Pipeline Python

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\argentina-retail-sales.exe download
.\.venv\Scripts\argentina-retail-sales.exe build
.\.venv\Scripts\argentina-retail-sales.exe validate
```

`all` ejecuta las cuatro etapas, incluida la exportación del dashboard. La descarga usa un temporal, verifica el contenido y
registra URL, bytes, hora y SHA-256 en `manifests/raw_sources.jsonl`.

## Dashboard HTML y assets locales

`argentina-retail-sales export` regenera `site/index.html`, `site/mobile.html` y
`site/assets/`. El sitio no descarga dependencias durante la navegación: usa Plotly Basic
`2.35.2`, su localización en español y las fuentes Space Grotesk e IBM Plex Mono desde el
paquete Python. El export falla si falta un archivo o no coincide con estos SHA-256:

| Asset | SHA-256 |
|---|---|
| `plotly-basic-2.35.2.min.js` | `138c2e81014b979dc00867a93da55b7605a17495ee78dd7afb433b7f021dfcfa` |
| `plotly-locale-es-2.35.2.js` | `1a20051d1983e522718de67dc977fe095727b6ff89bbe4a3c8c6251df841e981` |
| `fonts/space-grotesk-variable.ttf` | `acad6de1fc93436f5c0f1f4137751ef04f1aea3063e7036535970ffcfbd79f72` |
| `fonts/ibm-plex-mono-regular.ttf` | `6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46` |

Los originales versionados viven en `src/argentina_retail_sales/assets/`. No se deben
reemplazar sin actualizar versión, hashes, documentación y tests en el mismo cambio.

## SQL Server

```powershell
sqlcmd -S "<servidor>" -d "ArgentinaRetailSales" -E -b -i ".\sql\deploy.sql"
sqlcmd -S "<servidor>" -d "ArgentinaRetailSales" -E -b -Q "EXEC retail_ops.load_portfolio_csvs @portfolio_data_path=N'<ruta>\portfolio_data'; EXEC retail_ops.assert_published_quality;"
```

La cuenta del servicio SQL debe leer la ruta. Use un share accesible por SQL Server si la
instancia es remota. No incluya contrasenas en el comando o repositorio. Consulte
[`sql/README.md`](../sql/README.md) para transaccion, indices y recuperacion.

## Power BI

1. Abrir `powerbi\ArgentinaRetail.pbip`.
2. Configurar `ServerName` y `DatabaseName` sin guardar credenciales en archivos.
3. Actualizar y verificar que el gate sea `PASS`.
4. Reconciliar mayo de 2026 y los conteos contra `portfolio_data/`.
5. Revisar las cuatro paginas y crear/certificar el layout movil.
6. Guardar una copia como PBIX para GitHub Release; no agregar cache `.pbi/` ni PBIX al historial Git.

## Validacion local

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest --cov=argentina_retail_sales --cov-report=term-missing --cov-report=xml
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\powerbi\validate_pbip.ps1 -SkipTom
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\powerbi\validate_pbip.ps1
```

La ultima orden requiere Power BI Desktop y deserializa `model.bim` con TOM. Ninguna
variante ejecuta Power Query, DAX o render interactivo.

## CI

GitHub Actions y GitLab CI ejecutan Ruff, format, pytest con el threshold de cobertura y
el validador PBIP estructural. Los tests tambien revisan SQL estatico: esquemas, claves,
transaccion, gate, CTEs, ventanas, indices y ausencia de `SELECT *`.

## Recuperacion

| Falla | Comportamiento | Accion |
|---|---|---|
| Descarga incompleta | El temporal no reemplaza raw. | Reintentar `download`. |
| Contrato fuente incompatible | Build/validacion falla. | Revisar columnas; no editar raw. |
| Reconciliacion `HIGH` | Publicacion bloqueada. | Corregir fuente/pipeline; no bajar el gate. |
| `BULK INSERT` sin acceso | SQL registra batch fallido. | Corregir permiso/ruta y reintentar. |
| Carga SQL falla | Rollback; queda la version anterior. | Consultar `retail_ops.load_batch`. |
| PBIP estructural falla | CI bloquea. | Corregir modelo/referencia; reejecutar validator. |
| Refresh/render falla | No afecta CSV/SQL. | Revisar parametros y Power BI Desktop. |
