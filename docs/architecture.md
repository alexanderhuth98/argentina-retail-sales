# Arquitectura

## Flujo

```text
Datos Argentina / INDEC
        |
        v
dos CSV raw + URL + timestamp + SHA-256
        |
        v
contrato pandas: columnas, meses, tipos, no negativos
        |
        v
transformacion agregada + 11 reconciliaciones HIGH
        |
        v
cinco CSV de portfolio
        |
        v
staging temporal SQL Server -> tipos/claves/gate -> retail.*
        |
        +--> vistas analiticas e indices
        |
        v
Power BI Import: 5 hechos + 5 dimensiones + Medidas
        |
        v
4 paginas PBIR + validador estructural
```

## Capas y granos

| Capa | Grano | Responsabilidad |
|---|---|---|
| Raw | mes nacional por fuente | Snapshot oficial inmutable local. |
| Portfolio mensual | mes + formato | Titular nominal, constante e indices reales. |
| Mix | mes + formato + dimension | Pago, categoria o canal dentro del formato. |
| Calidad | fuente + control | Evidencia del gate de publicacion. |
| SQL Server | igual al CSV | Tipos, claves, checks, indices y publicacion atomica. |
| Power BI | estrella de hechos agregados | Contexto comun sin relaciones hecho-hecho. |

## Publicacion y fallo seguro

Python escribe los entregables solo despues de validar la fuente. SQL Server usa
`sp_getapplock`, tablas temporales, `TRY_CONVERT`, claves documentadas y una transaccion.
Si un contrato o control `HIGH` falla, se revierte el reemplazo y se conserva la ultima
publicacion valida. `retail_ops.load_batch` registra ejecuciones exitosas y fallidas.

## Modelo semantico

`Calendario` filtra los cuatro hechos temporales. `Formato` filtra los cinco hechos;
`MedioPago`, `Categoria` y `Canal` filtran solo el hecho correspondiente. Todas las
relaciones son uno a muchos, activas y en una direccion. No se relacionan hechos entre si.

Las medidas exigen un formato unico antes de calcular ventas, indices o shares. Esto
evita que una seleccion accidental convierta dos encuestas en una medida de mercado.

## Seguridad y versionado

- Raw, caches, PBIX y estados locales `.pbi/` estan ignorados.
- El modelo usa `ServerName` y `DatabaseName`; la autenticacion no se guarda.
- Los manifests publicos incluyen hashes, no tokens.
- PBIP/PBIR, SQL, tema, validator y documentacion son texto revisable.
