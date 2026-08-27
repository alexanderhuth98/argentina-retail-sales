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

`all` ejecuta las tres etapas. La descarga usa un temporal, verifica el contenido y
registra URL, bytes, hora y SHA-256 en `manifests/raw_sources.jsonl`.

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
