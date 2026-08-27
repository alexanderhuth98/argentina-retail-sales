# Metodologia

## Unidad de analisis

Cada fuente contiene una observacion mensual nacional. Supermercados y autoservicios
mayoristas representan universos de encuesta distintos y no se consolidan en una unica
cifra de mercado.

## Unidades

- `ventas_precios_corrientes` y `ventas_precios_constantes`: millones de pesos.
- Detalle por canal, pago y categoria: miles de pesos corrientes.
- Series original, desestacionalizada y tendencia-ciclo: indice base 2017 = 100.

El pipeline conserva estas diferencias y reconcilia el titular nominal multiplicado por
1.000 contra los totales detallados.

## Lectura de ventas reales

- Variacion interanual: indice real original contra el mismo mes del ano anterior.
- Variacion mensual: indice real desestacionalizado contra el mes anterior.
- Tendencia-ciclo: descripcion de regimen; los extremos pueden revisarse.
- Anos parciales: se comparan con el mismo numero de meses del ano anterior.

## Comparaciones

Se permiten comparaciones de crecimiento, indices respecto de la propia base y shares
dentro de cada formato. No se interpreta la razon de facturacion entre formatos como
market share ni como migracion causal de clientes.

## Faltantes

El detalle mayorista de salon y canal online termina en agosto de 2022. Desde septiembre
de 2022 ambos campos se mantienen nulos y quedan fuera de rankings y shares observados.
