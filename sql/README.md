# Capa SQL Server

## Contrato

La capa carga sin recalcular los cinco CSV validados de `portfolio_data/`. Las tablas de
`retail` conservan su grano, tipos, claves, disponibilidad y unidad original. El esquema
`retail_ops` conserva el historial de intentos y publica mediante una transaccion unica.

Requisitos: SQL Server 2017 o posterior, `BULK INSERT` habilitado y una cuenta del
servicio con lectura sobre la carpeta de CSV. La ruta se entrega al procedimiento; no se
versionan credenciales ni rutas personales.

## Despliegue y carga

Desde `sqlcmd`, ejecute los scripts en modo SQLCMD:

```powershell
sqlcmd -S "<servidor>" -d "ArgentinaRetailSales" -E -b -i ".\sql\deploy.sql"
sqlcmd -S "<servidor>" -d "ArgentinaRetailSales" -E -b -Q "EXEC retail_ops.load_portfolio_csvs @portfolio_data_path=N'<ruta-compartida>\portfolio_data'; EXEC retail_ops.assert_published_quality;"
```

Use `-G` o el mecanismo de autenticacion administrado por su organizacion cuando no
corresponda autenticacion integrada. Nunca incluya contrasenas en comandos versionados.

## Publicacion atomica

1. `sp_getapplock` evita dos cargas simultaneas.
2. Los cinco archivos entran a tablas temporales de texto.
3. Se validan tipos, dominios, claves, nulos estructurales y presencia de controles `HIGH`.
4. Cualquier `HIGH` distinto de `PASS` aborta antes de tocar las tablas publicadas.
5. El reemplazo completo y el estado `PUBLISHED` ocurren en una sola transaccion.
6. Ante error se revierte todo y se registra un batch `FAILED`; la publicacion anterior queda intacta.

Reejecutar el mismo conjunto produce el mismo estado de negocio con un nuevo
`load_batch_id`, por lo que la operacion es idempotente y auditable.

## Modelo y rendimiento

- Las claves primarias materializan el grano documentado.
- Los indices secundarios priorizan formato, dimension y mes descendente.
- `v_payment_mix_change` y `v_category_mix_change` usan `LAG` dentro de cada formato.
- `v_channel_availability` expone el ultimo mes realmente observado.
- No hay una vista que sume formatos: sus universos de encuesta no forman un mercado unico.

Revise planes despues de cambios de volumen y actualice estadisticas tras cargas muy
grandes. Los CSV actuales son pequenos; particionar tablas agregaria complejidad sin un
beneficio medible.

## Recuperacion

| Falla | Accion |
|---|---|
| Permiso o ruta de `BULK INSERT` | Dar lectura a la cuenta del servicio y reintentar. |
| Contrato, tipo o clave invalida | Regenerar los CSV con el pipeline; no editar staging. |
| Gate `HIGH` fallido | Corregir la fuente/pipeline; no bajar el gate. |
| Carga concurrente | Esperar al proceso activo y reejecutar. |
| Batch `FAILED` | Consultar `retail_ops.load_batch.error_message`; la version previa sigue publicada. |
