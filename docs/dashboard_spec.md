# Especificacion del dashboard Power BI

## Business goal

Explicar si el retail argentino crece en terminos reales y como cambia su composicion por
formato, medio de pago, canal y categoria, sin convertir universos de encuesta distintos
en una cifra de mercado no defendible.

## Audience

Gerencia comercial, responsables de trade marketing y analistas de ventas. El dashboard
prioriza lectura ejecutiva y mantiene disponible el detalle de calidad para analistas.

## KPIs

| KPI | Unidad | Regla |
|---|---|---|
| Indice real original | base 2017=100 | Un solo formato; ultimo mes del contexto. |
| Variacion real interanual | porcentaje | Indice original contra igual mes anterior. |
| Variacion real mensual SA | porcentaje | Indice desestacionalizado contra mes anterior. |
| Ventas nominales | millones ARS corrientes | Nunca comparte eje con indices. |
| Share de pago/categoria/canal | porcentaje | Denominador dentro de mes y formato. |
| Cambio de share | puntos porcentuales | Share contra igual mes anterior. |
| Fecha efectiva | fecha | Maximo mes realmente observado por fuente/visual. |
| Gate de calidad | PASS/BLOCKED | Requiere al menos un `HIGH` y cero fallas `HIGH`. |

Las medidas de negocio devuelven `BLANK` si el contexto incluye ambos formatos. No se
presenta su suma ni una razon de facturacion como market share.

## Filters

- Formato: selector obligatorio y visible, con supermercados o autoservicios mayoristas.
- Periodo: ano desde `Calendario`; el eje permite bajar a mes.
- Medio de pago, categoria y canal: seleccion mediante leyenda/visual.
- Categoria: selector dedicado para narrativa y detalle.
- Disponibilidad: `is_observed` se aplica dentro de medidas de canal, no como reemplazo por cero.

## Pagina 1: Panorama ejecutivo

- Top: indice real, variacion real interanual, variacion desestacionalizada mensual y ventas nominales.
- Middle: tendencia mensual del indice original y tendencia-ciclo.
- Bottom: ventas nominales en un eje separado.
- Pregunta: la facturacion corriente coincide con recuperacion real?

## Pagina 2: Medios de pago

- Top: ultimo share de efectivo, debito, credito y otros.
- Middle: lineas de participacion mensual por medio.
- Bottom: cambio interanual en puntos porcentuales.
- Small multiples por formato no son necesarios porque el selector impide consolidarlos;
  la comparacion se realiza alternando el formato con el mismo layout.

## Pagina 3: Categorias

- Top: ventas nominales, share, variacion nominal interanual y fecha efectiva.
- Middle: mix por categoria, con foco narrativo sugerido en almacen, bebidas, panaderia,
  lacteos y carnes.
- Bottom: ranking de share del ultimo mes.
- Advertencia permanente: variacion nominal por categoria no equivale a volumen.

## Pagina 4: Canales y calidad

- Top: share online, ultima fecha observada, fallas `HIGH` y gate de publicacion.
- Middle: mix online/salon; la serie mayorista termina en agosto de 2022.
- Bottom: tabla de fuente, severidad, estado, control y detalle.
- La cobertura debe explicar el faltante mayorista, no ocultarlo.

## Layout y paleta

- Lienzo 16:9 de `1280 x 720`.
- Orden estable: KPIs arriba, tendencias al centro y breakdowns/calidad abajo.
- Supermercados: azul profundo `#164B73`; mayoristas: terracota `#B65F45`.
- Acentos: verde petroleo `#2D7C78`, ocre `#D2A449`; contexto `#667680`.
- Fondo marfil `#F5F1E8`, tarjetas `#FFFEFA`, texto `#183044`.
- Rojo se reserva para estados bloqueantes; no se usa como color decorativo.

## Interactions, drilldowns y tooltips

- Selecciones de leyenda y barras filtran los visuales de la pagina.
- `defaultDrillFilterOtherVisuals` mantiene el contexto al bajar de ano a mes.
- No hay drill-through a filas transaccionales porque la fuente es mensual agregada.
- Tooltips mejorados deben incluir formato, mes, unidad, valor y fecha efectiva.
- Titulos declaran `nominal`, `real`, `%`, `pp` y limitaciones de cobertura.
- No se permiten ejes duales que mezclen ARS nominales con indices reales.

## Mobile behavior

El orden movil es selector, cuatro KPIs, tendencia y breakdown. Las tarjetas deben ocupar
una columna y los rankings deben limitar etiquetas antes de habilitar scroll. El PBIR
versionado no certifica un layout movil especifico porque esa disposicion requiere render
en Power BI Desktop; se debe crear/revisar antes de publicar y capturar evidencia.

## Acceptance criteria

- Las cuatro paginas abren y actualizan desde SQL Server sin credenciales versionadas.
- Todos los KPIs quedan en blanco con mas de un formato seleccionado.
- Los totales visibles reconcilian con los cinco CSV.
- La fecha de canal mayorista no supera agosto de 2022.
- El gate muestra `PASS` solo con todos los controles `HIGH/PASS`.
- El validador PowerShell y pytest aprueban estructura, referencias y contratos.
- Escritorio y movil se revisan manualmente en Power BI Desktop antes de publicar.
