# Datos curados para portfolio

El pipeline genera en esta carpeta CSV agregados y reproducibles para Power BI. No se
editan manualmente.

Las ventas detalladas se expresan en miles de pesos corrientes. Los indices reales usan
base 2017 = 100. Los valores ausentes de canal mayorista desde septiembre de 2022 son
faltantes estructurales y no equivalen a cero.

| Archivo | Grano | Filas del snapshot |
|---|---|---:|
| `monthly_summary.csv` | mes y formato | 226 |
| `payment_mix.csv` | mes, formato y medio de pago | 904 |
| `category_mix.csv` | mes, formato y categoria | 2.373 |
| `channel_mix.csv` | mes, formato y canal | 452 |
| `quality_checks.csv` | fuente y control | 11 |

El corte observado llega a mayo de 2026. Los cinco archivos son el contrato de carga SQL
y la evidencia de validacion estructural de Power BI; no deben editarse manualmente.
