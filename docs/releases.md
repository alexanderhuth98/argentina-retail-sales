# Publicacion de entregables

El historial Git conserva codigo, PBIP textual, SQL y datos agregados versionables. Los
binarios locales se publican como activos de GitHub Release, no como blobs del repositorio.

## Proxima version `v1.1.0`

Esta rama prepara la version `1.1.0` del paquete Python. El tag y la GitHub Release
`v1.1.0` se crean despues del merge y de completar el checklist; este documento no implica
que ya esten publicados. Hasta entonces, la ruta de
[ultima release](https://github.com/alexanderhuth98/argentina-retail-sales/releases/latest)
resuelve a `v1.0.0`.

- `powerbi/ArgentinaRetail.pbix`
- `outputs/release-v1.1.0/SHA256SUMS.txt`

`ArgentinaRetail.pbix` se genera localmente con Power BI Desktop despues de desplegar y
cargar SQL Server. El archivo queda ignorado por `.gitignore`; el Release conserva el
binario y su hash para descarga publica.

El `SCHEMA_VERSION = 1.0.0` de `config.py` identifica el contrato de los datos y no la
version del paquete ni del release.

## Release anterior `v1.0.0`

La release inmutable publicada anteriormente se conserva en
[`v1.0.0`](https://github.com/alexanderhuth98/argentina-retail-sales/releases/tag/v1.0.0).
Sus binarios y hashes corresponden a ese tag, no al codigo actual de esta rama.

## Checklist previo

1. Ejecutar el pipeline Python y confirmar los cinco CSV de `portfolio_data/`.
2. Desplegar `sql/deploy.sql` y ejecutar `retail_ops.load_portfolio_csvs`.
3. Confirmar `11` controles `HIGH` en `PASS` con `retail_ops.assert_published_quality`.
4. Abrir `powerbi/ArgentinaRetail.pbip` en Power BI Desktop, refrescar y revisar las cuatro paginas.
5. Guardar una copia como `powerbi/ArgentinaRetail.pbix`.
6. Ejecutar `scripts/package_release.ps1` desde la raiz.
7. Adjuntar `ArgentinaRetail.pbix` y `SHA256SUMS.txt` al Release de GitHub.

No adjuntar raw data, credenciales, caches `.pbi/`, PBIX intermedios ni conexiones locales.
