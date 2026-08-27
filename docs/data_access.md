# Acceso a datos

## Fuentes oficiales

| Fuente | URL directa | Frecuencia |
|---|---|---|
| Supermercados | `https://infra.datos.gob.ar/catalog/sspm/dataset/455/distribution/455.1/download/ventas-totales-supermercados-2.csv` | mensual |
| Autoservicios mayoristas | `https://infra.datos.gob.ar/catalog/sspm/dataset/456/distribution/456.1/download/ventas-totales-autoservicios-mayoristas.csv` | mensual |

El pipeline descarga ambos archivos con escritura temporal, calcula SHA-256 y registra
la fecha de recuperacion. Los archivos raw no se versionan.

## Observacion de metadata

El rango temporal informado en la metadata general del catalogo puede quedar atrasado
respecto del CSV. Por eso la fecha maxima se obtiene del snapshot y se valida contra una
secuencia mensual continua.
