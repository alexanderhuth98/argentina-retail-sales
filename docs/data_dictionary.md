# Diccionario de datos publicados

## `monthly_summary.csv`

Grano: un mes y formato. Clave: `month, retail_format`. Filas actuales: `226`.

| Campo | Tipo | Unidad/descripcion |
|---|---|---|
| `month` | fecha | Primer dia del mes. |
| `retail_format` | texto | `supermarkets` o `wholesale`. |
| `nominal_sales_million_ars` | decimal | Millones de ARS corrientes. |
| `constant_sales_million_ars` | decimal | Millones de ARS constantes de la fuente. |
| `real_sales_index_original` | decimal | Indice original, base 2017=100. |
| `real_sales_index_sa` | decimal | Indice desestacionalizado. |
| `real_sales_index_trend` | decimal | Tendencia-ciclo. |
| `nominal_sales_yoy_pct` | decimal nullable | Variacion nominal interanual, porcentaje. |
| `real_sales_yoy_pct` | decimal nullable | Variacion real interanual, porcentaje. |
| `real_sales_sa_mom_pct` | decimal nullable | Variacion mensual SA, porcentaje. |
| `is_partial_year` | booleano | Verdadero para el ultimo ano incompleto. |

## `payment_mix.csv`

Grano: mes, formato y medio. Clave: `month, retail_format, payment_method`. Filas: `904`.
`sales_thousand_ars` esta en miles de ARS corrientes; `share_pct` es participacion dentro
del total mensual del formato. Los cuatro medios observados suman aproximadamente 100%.

## `category_mix.csv`

Grano: mes, formato y categoria. Clave: `month, retail_format, category`. Filas: `2.373`.
`sales_thousand_ars` y `share_pct` son nominales. `comparable_across_formats` excluye
`prepared_food` de comparaciones cuando no existe una definicion equivalente.

## `channel_mix.csv`

Grano: mes, formato y canal. Clave: `month, retail_format, channel`. Filas: `452`.
`is_observed` distingue datos reales de faltantes estructurales. Si es falso,
`sales_thousand_ars` y `share_pct` son nulos. Mayoristas queda no observado desde 2022-09.

## `quality_checks.csv`

Grano: fuente y control. Clave: `source, check`. Filas: `11`.

| Campo | Descripcion |
|---|---|
| `source` | Formato/fuente evaluada. |
| `check` | Identificador estable del control. |
| `severity` | `HIGH` bloquea publicacion. |
| `status` | `PASS` o `FAIL`. |
| `detail` | Regla evaluada en lenguaje legible. |

## Reglas comunes

- Los meses son continuos y comienzan el dia 1.
- No se imputan nulos ni se convierten en cero.
- Los porcentajes se almacenan en escala 0-100 en CSV/SQL; las medidas DAX los dividen
  por 100 para usar formato porcentual.
- Los formatos no se agregan en un total de mercado.
