# Publicacion de entregables

El historial Git conserva codigo, PBIP textual, SQL y datos agregados versionables. Los
binarios locales se publican como activos de GitHub Release, no como blobs del repositorio.

## Activos de la version `v1.0.0`

- `powerbi/ArgentinaRetail.pbix`
- `outputs/release-v1.0.0/SHA256SUMS.txt`

`ArgentinaRetail.pbix` se genera localmente con Power BI Desktop despues de desplegar y
cargar SQL Server. El archivo queda ignorado por `.gitignore`; el Release conserva el
binario y su hash para descarga publica.

## Checklist previo

1. Ejecutar el pipeline Python y confirmar los cinco CSV de `portfolio_data/`.
2. Desplegar `sql/deploy.sql` y ejecutar `retail_ops.load_portfolio_csvs`.
3. Confirmar `11` controles `HIGH` en `PASS` con `retail_ops.assert_published_quality`.
4. Abrir `powerbi/ArgentinaRetail.pbip` en Power BI Desktop, refrescar y revisar las cuatro paginas.
5. Guardar una copia como `powerbi/ArgentinaRetail.pbix`.
6. Ejecutar `scripts/package_release.ps1` desde la raiz.
7. Adjuntar `ArgentinaRetail.pbix` y `SHA256SUMS.txt` al Release de GitHub.

No adjuntar raw data, credenciales, caches `.pbi/`, PBIX intermedios ni conexiones locales.
