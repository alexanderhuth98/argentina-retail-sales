# Pulso del retail argentino

Caso de Data Analytics sobre ventas mensuales de supermercados y autoservicios
mayoristas de Argentina. Separa crecimiento nominal de evolucion real y analiza
el cambio en canales, medios de pago y grupos de articulos desde 2017.

## Problema de negocio

Las ventas expresadas en pesos pueden crecer aun cuando el volumen real se contrae.
El proyecto busca responder:

1. ¿Las ventas reales se recuperan o el crecimiento observado es principalmente nominal?
2. ¿Como cambio el uso de efectivo, debito, credito y otros medios de pago?
3. ¿Que categorias ganaron o perdieron participacion dentro de cada formato?
4. ¿El canal online de supermercados mantuvo el salto observado durante la pandemia?
5. ¿Como evolucionaron supermercados y mayoristas respecto de su propia base 2017?

## Alcance defendible

- Los formatos se analizan por separado y se comparan mediante tasas, indices y shares.
- No se suman supermercados y mayoristas porque puede existir doble conteo comercial.
- Las ventas por categoria son nominales; no se presentan como volumen fisico.
- El detalle de canal mayorista se publica solo hasta agosto de 2022, ultimo mes observado.
- Los faltantes no se imputan ni se reemplazan por cero.

## Fuentes

Datos oficiales mensuales publicados en Datos Argentina, con fuente INDEC y licencia
CC BY 4.0:

- Ventas en supermercados.
- Ventas en autoservicios mayoristas.

El snapshot validado cubre enero de 2017 a mayo de 2026. La metadata del catalogo
puede mostrar un rango desactualizado; el pipeline usa las fechas observadas en los CSV.

## Stack

Implementado: `Python 3.11` | `pandas`

Siguiente hito: `SQL Server` | `Power BI`

## Ejecutar

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\argentina-retail-sales.exe all
```

Etapas disponibles:

```powershell
.\.venv\Scripts\argentina-retail-sales.exe download
.\.venv\Scripts\argentina-retail-sales.exe build
.\.venv\Scripts\argentina-retail-sales.exe validate
```

## Outputs para portfolio

| Archivo | Grano |
|---|---|
| `monthly_summary.csv` | mes y formato comercial |
| `payment_mix.csv` | mes, formato y medio de pago |
| `category_mix.csv` | mes, formato y categoria |
| `channel_mix.csv` | mes, formato y canal |
| `quality_checks.csv` | control de calidad ejecutado |

Consulte [metodologia](docs/methodology.md), [acceso a datos](docs/data_access.md) y
[especificacion del dashboard](docs/dashboard_spec.md).
