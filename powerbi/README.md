# Power BI

## Objetivo y audiencia

- Objetivo: separar crecimiento nominal de desempeño real y explicar cambios de pago,
  categoria y canal dentro de cada formato del retail argentino.
- Audiencia: gerencia comercial, trade marketing y analistas de ventas.
- Regla central: supermercados y mayoristas son universos distintos. Las medidas de
  negocio devuelven `BLANK` cuando no existe exactamente un formato en contexto.
- Fuente: las cinco tablas tipadas de SQL Server, publicadas solo tras superar el gate
  `HIGH`; los CSV se usan como contrato estructural del validador.

## Artefactos

- `ArgentinaRetail.pbip`: punto de entrada versionable.
- `ArgentinaRetail.SemanticModel/model.bim`: 11 tablas, 12 relaciones y medidas DAX.
- `ArgentinaRetail.Report/`: cuatro paginas y 33 visuales nativos.
- `theme.json`: paleta editorial; azul profundo para supermercados y terracota para
  mayoristas, con gris para contexto y alertas reservadas.
- `validate_pbip.ps1`: JSON, contratos CSV, tipos, relaciones, referencias visuales,
  layout, rutas, credenciales y deserializacion TOM opcional.

No se incluyen PBIX, cache, credenciales ni rutas locales.

## Conexion

`ServerName` y `DatabaseName` son parametros M obligatorios. Sus valores versionados son
`localhost` y `ArgentinaRetailSales`, sin usuario ni contrasena. Cambielos en **Transformar
datos > Administrar parametros** y use el mecanismo de autenticacion de Power BI Desktop;
no guarde secretos en el proyecto.

Todas las consultas usan `Value.NativeQuery` con columnas explicitas. Las dimensiones de
formato, pago, categoria y canal son tablas de referencia pequenas; `Calendario` se genera
desde el rango publicado. No existen relaciones entre hechos ni filtros bidireccionales.

## Paginas

| Pagina | KPI superior | Tendencia central | Desglose inferior |
|---|---|---|---|
| Panorama ejecutivo | indice real, YoY real, MoM desestacionalizado, ventas nominales | indice original y tendencia | ventas nominales, en eje separado |
| Medios de pago | shares de efectivo, debito, credito y otros | mix mensual | cambio interanual en puntos porcentuales |
| Categorias | ventas, share, variacion nominal y fecha efectiva | mix por categoria | ranking del ultimo mes |
| Canales y calidad | share online, cobertura, fallas HIGH y gate | mix de canal | detalle de controles |

## Filtros e interacciones

- Segmentadores visibles de formato y periodo; categorias agrega su propio selector.
- Seleccionar una serie filtra el resto de la pagina mediante interacciones nativas.
- Tooltips mejorados muestran fecha, formato, unidad y valor; los titulos distinguen
  `ARS nominales`, `indice real`, `%` y `pp`.
- Drill-down temporal: ano a mes mediante `Calendario`; no se habilita drill-through a
  detalle inexistente.
- El canal mayorista termina visualmente en agosto de 2022 porque los nulos estructurales
  se conservan y `Share canal` filtra `is_observed = TRUE`.

El lienzo 16:9 sigue KPI arriba, tendencia al centro y breakdown abajo. El orden de
lectura permite una columna movil, pero PBIR no incluye un layout movil certificado: debe
crearse/revisarse en Power BI Desktop antes de publicar, con tarjetas, tendencia y detalle
en ese orden.

## Validacion

Validacion estructural portable:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\powerbi\validate_pbip.ps1 -SkipTom
```

Si una politica `AllSigned` bloquea archivos locales, use entrada estandar:

```powershell
$env:PBIP_SKIP_TOM='1'; cmd.exe /d /c "type powerbi\validate_pbip.ps1 | powershell.exe -NoProfile -Command -"
```

Validacion TOM cuando Power BI Desktop esta instalado:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\powerbi\validate_pbip.ps1
```

El script no ejecuta Power Query, DAX ni renderiza el lienzo. Despues de desplegar/cargar
SQL Server, abra `ArgentinaRetail.pbip`, configure parametros, actualice, compruebe los
totales contra `portfolio_data/`, revise escritorio/movil y guarde el PBIP.
