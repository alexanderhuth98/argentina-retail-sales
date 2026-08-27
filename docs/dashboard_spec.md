# Especificacion del dashboard Power BI

## Business goal

Explicar si el retail argentino crece en terminos reales y como cambia su composicion
por formato, medio de pago, canal y categoria.

## Audience

Gerencia comercial, responsables de trade marketing y analistas de ventas.

## Pagina 1: panorama ejecutivo

- KPIs: indice real, variacion real interanual, variacion desestacionalizada mensual y ventas nominales.
- Tendencia mensual de indices reales por formato.
- Separacion visual explicita entre nominal y real.
- Filtro: formato y periodo.

## Pagina 2: medios de pago

- Share de efectivo, debito, credito y otros medios.
- Cambio en puntos porcentuales contra el ano anterior.
- Small multiples por formato.

## Pagina 3: categorias

- Mix nominal por grupo de articulos.
- Variacion interanual nominal con advertencia de inflacion por categoria.
- Foco de storytelling en almacen, bebidas, panaderia, lacteos y carnes.

## Pagina 4: canales y calidad

- Share online de supermercados desde 2017.
- Mayoristas solo hasta agosto de 2022.
- Matriz de disponibilidad y controles de reconciliacion.

## Diseno

- Paleta: azul profundo para supermercados, terracota para mayoristas y gris para contexto.
- Tooltips con fuente, unidad, fecha efectiva y disponibilidad.
- Nada de ejes duales para mezclar pesos nominales con indices reales.
- Navegacion y tarjetas adaptadas a una columna en movil.

## Hito de implementacion

### 1. Capa SQL Server

- Cargar los cinco CSV validados en el esquema `retail` sin recalcular las metricas de Python.
- Crear tablas `monthly_summary`, `payment_mix`, `category_mix`, `channel_mix` y
  `quality_checks` con fechas y tipos numericos explicitos.
- Definir claves unicas segun el grano documentado y conservar `is_observed` como indicador
  de disponibilidad.
- Ejecutar la carga solo despues de que todos los controles `HIGH` tengan estado `PASS`.

### 2. Modelo Power BI

- Importar desde SQL Server y relacionar los hechos con una tabla calendario y dimensiones
  de formato, pago, categoria y canal.
- Mantener las medidas nominales, reales y de participacion separadas por unidad.
- Mostrar la fecha maxima observada por visual; el canal mayorista debe terminar en agosto
  de 2022 aunque las otras paginas lleguen a mayo de 2026.
- Validar totales y KPIs contra los CSV antes de publicar el PBIX.

### 3. Criterio de cierre

- Las cuatro paginas funcionan en escritorio y movil.
- Los filtros no permiten sumar ambos formatos como una unica cifra de mercado.
- La pagina de calidad expone fuente, cobertura, faltantes estructurales y resultado de los
  controles de reconciliacion.
- El repositorio incluye capturas y un enlace al dashboard publicado, pero no credenciales
  ni archivos de conexion locales.
