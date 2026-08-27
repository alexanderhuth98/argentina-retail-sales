# SQL highlights

El modelo completo esta en `sql/`. Estas consultas muestran las decisiones principales.

## 1. Publicacion con gate bloqueante

```sql
IF NOT EXISTS (
    SELECT 1
    FROM #quality_checks AS quality_check
    WHERE quality_check.severity = N'HIGH'
) OR EXISTS (
    SELECT 1
    FROM #quality_checks AS quality_check
    WHERE quality_check.severity = N'HIGH'
      AND quality_check.status <> N'PASS'
)
    THROW 51002, 'Publication blocked', 1;
```

El control ocurre antes de borrar tablas publicadas y dentro de la misma transaccion.

## 2. Cambio de pago con ventana

```sql
WITH payment_history AS (
    SELECT
        payment.month,
        payment.retail_format,
        payment.payment_method,
        payment.share_pct,
        LAG(payment.share_pct, 12) OVER (
            PARTITION BY payment.retail_format, payment.payment_method
            ORDER BY payment.month
        ) AS prior_year_share_pct
    FROM retail.payment_mix AS payment
)
SELECT
    history.month,
    history.retail_format,
    history.payment_method,
    history.share_pct - history.prior_year_share_pct AS share_yoy_change_pp
FROM payment_history AS history;
```

La particion evita cruzar formatos o medios; la diferencia se expresa en puntos porcentuales.

## 3. Cobertura efectiva de canal

```sql
SELECT
    channel_row.month,
    channel_row.retail_format,
    channel_row.channel,
    channel_row.is_observed,
    MAX(CASE WHEN channel_row.is_observed = 1 THEN channel_row.month END) OVER (
        PARTITION BY channel_row.retail_format, channel_row.channel
    ) AS latest_observed_month
FROM retail.channel_mix AS channel_row;
```

La fecha maxima se calcula solo con observaciones reales. Los nulos mayoristas posteriores
a agosto de 2022 permanecen visibles como cobertura, no como ventas cero.

## Optimizacion

- Claves clustered materializan cada grano de negocio.
- Cinco indices cubren filtros de formato, dimension y mes descendente.
- Las consultas proyectan columnas explicitas y no usan `SELECT *`.
- No se usa `MERGE`; el reemplazo completo transaccional evita sus riesgos de concurrencia.
- El volumen actual no justifica particionamiento; revisar planes/estadisticas si crece.
