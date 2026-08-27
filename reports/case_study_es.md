# Caso de estudio: pulso del retail argentino

## Resumen ejecutivo

En mayo de 2026 las ventas nominales crecieron interanualmente `25,9%` en supermercados y
`23,7%` en autoservicios mayoristas, pero los indices reales originales cayeron `0,7%` y
`2,3%`. La senal mensual desestacionalizada fue positiva (`0,9%` y `2,3%`), sin revertir
por si sola el nivel real: ambos indices quedaron cerca de `80,5` sobre base 2017=100.

La composicion tambien cambio. En supermercados el credito lidero con `45,0%`; efectivo
quedo en `16,5%`. En mayoristas, otros medios alcanzo `32,3%`. Almacen concentro `27,1%`
del mix nominal de supermercados y `44,4%` del mayorista. El share online de supermercados
fue `3,43%`; el mayorista no se actualiza desde agosto de 2022.

## Objetivos

- Distinguir facturacion corriente de desempeno real.
- Describir cambios de pago, categoria y canal dentro de cada formato.
- Mantener visibles cobertura, unidades y calidad antes de decidir.

## Metodologia

Se procesaron dos series oficiales mensuales de enero de 2017 a mayo de 2026. El pipeline
valida contratos, continuidad, no negatividad y reconciliaciones. Las ventas detalladas se
expresan en miles de ARS corrientes; los titulares nominales y constantes, en millones; los
indices reales usan 2017=100. Los formatos no se suman porque corresponden a universos de
encuesta distintos. Mayo de 2026 pertenece a un ano parcial.

## Hallazgos

| Indicador, mayo 2026 | Supermercados | Mayoristas |
|---|---:|---:|
| Ventas nominales, millones ARS | `2.502.789,7` | `388.237,1` |
| Variacion nominal interanual | `25,9%` | `23,7%` |
| Indice real original | `80,5` | `80,6` |
| Variacion real interanual | `-0,7%` | `-2,3%` |
| Variacion real mensual SA | `0,9%` | `2,3%` |

En pagos, el cambio interanual mas grande de supermercados fue otros medios (`+3,17 pp`),
mientras debito cedio `2,72 pp`. En mayoristas, efectivo aumento `2,92 pp` y debito cayo
`4,44 pp`. Son cambios de composicion, no evidencia de causalidad.

Las cinco categorias principales de supermercados fueron almacen (`27,1%`), carnes
(`14,6%`), limpieza y cuidado personal (`13,1%`), lacteos (`11,3%`) y bebidas (`9,1%`).
En mayoristas lideraron almacen (`44,4%`) y limpieza/cuidado personal (`25,9%`). Estos
shares son nominales y pueden reflejar precios relativos ademas de cantidades.

## KPIs y calidad

El dashboard separa indice real, variacion real interanual, variacion desestacionalizada,
ventas nominales, shares, puntos porcentuales y fecha maxima observada. Los `11` controles
`HIGH` estan en `PASS`. El gate confirma las reglas implementadas; no prueba que la fuente
sea perfecta ni completa.

## Recomendaciones

- Gestionar cada formato por separado y usar indices reales para metas de recuperacion.
- Investigar el crecimiento de otros medios sin atribuirlo a una causa no observada.
- Revisar margen, unidades y precios antes de convertir mix nominal en decisiones de surtido.
- Mantener la fecha efectiva del canal en toda presentacion; no completar mayoristas con cero.

## Riesgos

- 2026 es parcial y los extremos de tendencia-ciclo pueden revisarse.
- No hay unidades, margen, tickets, clientes ni causalidad promocional.
- Los formatos no representan un market share combinado.
- El canal mayorista posterior a agosto de 2022 no esta observado.

## Proximos pasos

Desplegar/cargar SQL Server, refrescar el PBIP, reconciliar los KPIs visibles con los CSV y
certificar el render de escritorio y movil en Power BI Desktop antes de publicar.
