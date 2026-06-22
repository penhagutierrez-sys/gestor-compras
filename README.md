# Gestor de Compras 2.0

App de **escritorio** (Python) para **FERRETERÍA SOLUCENTER LTDA** que convierte el historial
de ventas y el stock en **decisiones de compra**: qué reponer, cuánto pedir, dónde hay capital
inmovilizado, y cómo consolidar los pedidos en camión.

> Repo privado. El **código** vive aquí; los **datos** (ventas, stock, proveedores) son
> confidenciales y quedan **fuera del repo** (ver `.gitignore`) — se configuran en `config.py`.

---

## Qué hace

- **Salud de inventario** por producto, basada en **días de cobertura** (stock ÷ demanda diaria),
  como los líderes del retail (Lowe's, Sodimac, RELEX, Slim4):
  Quiebre · Crítico · Bajo · Saludable · Sobrestock · Sin rotación.
- **Clasificación ABC/XYZ** (valor económico × variabilidad de demanda) y pronóstico por media móvil.
- **Punto de reorden** por nivel de servicio según clase ABC (A 98% / B 95% / C 90%),
  con stock de seguridad y cantidad sugerida (política s,S). *Lead time configurable.*
- **Dashboard reactivo** (estilo Salesforce Lightning): medidores KPI, barra de salud y
  capital inmovilizado que se recalculan según el estado/sucursal/categoría seleccionados.
- **Filtros**: por **sucursal** (recalcula todo para esa sucursal), categoría, familia y búsqueda.
- **Consolidación en camión**: agrupa los sugeridos por **proveedor/origen** (Chilemat/Santiago,
  Cemento/Concepción, Polines/Los Ángeles) y estima camiones **Volvo FH500 / FM460**
  (~28 t por viaje). Peso por **catálogo web** (Sodimac/Easy/Construmart) → nombre → estimado.
- **Traslados entre sucursales**: sugiere mover el **excedente** de una sucursal (sobrestock /
  sin rotación) a otra donde **falta** (bajo punto de reorden), antes de comprar.
- **Exportar a Excel** la vista actual.

## Honestidad / supuestos (importante)

- Datos de ventas: solo **ene–may de 2025 y 2026** → sin estacionalidad de 12 meses.
- **Lead time** es un supuesto configurable (no dato real por proveedor).
- **Peso/volumen**: real solo en ~10% de los nombres + catálogo web; el resto es **estimado**
  (preciso en cemento). La UI rotula la confianza.
- El export de stock no trae todas las sucursales ni los quiebres reales (stock 0) →
  se muestran como "sin dato".

## Cómo correr

1. Instalar Python 3.12 y las dependencias:
   ```
   pip install -r requirements.txt
   ```
   (La interfaz usa la fuente **Inter**; si no está instalada, se ve con otra fuente.)
2. Revisar las **rutas de datos** en `config.py` (ventas, stock, proveedores).
3. Abrir la app:
   - Doble clic en **`Abrir Gestor de Compras.bat`**, o
   - `python app.py`
   - Sin ventana (terminal): `python main.py`

## Datos que necesita (no incluidos en el repo)

Configurados en `config.py`:
- **Ventas**: Excel transaccional (`BBDD_Ventas_Reclasificada_2026.xlsx`, hoja "BD Vta").
- **Stock**: export de Power BI (Datos resumidos) con `SUCURSAL, NOMBRE_PRODUCTO, STOCK_FISICO`.
- **Proveedores**: maestro `Datos Maepro` (`CODIGO → NOMBRE PROVEEDOR`).

## Estructura

```
gestor-compras/
├─ app.py            # ventana de escritorio (Tkinter + ttkbootstrap)
├─ main.py           # corre el motor sin ventana (terminal)
├─ config.py         # rutas de datos y parámetros (lead time, umbrales, camión, pesos…)
├─ motor/
│  ├─ cargar_datos.py  # lee ventas, stock y proveedores
│  ├─ analisis.py      # ABC/XYZ, pronóstico, σ de demanda
│  ├─ ordenes.py       # cobertura, estado de inventario, punto de reorden
│  ├─ consolidar.py    # consolidación por proveedor/origen y camiones
│  ├─ pipeline.py      # orquesta carga + clasificación (cacheado)
│  └─ exportar.py      # exporta a Excel
├─ data/             # catálogo de pesos web (los datos crudos NO se versionan)
└─ salidas/          # OCs/Excel generados (no se versiona)
```

## Stack

Python 3.12 · pandas · openpyxl · ttkbootstrap (Tkinter) · GitHub.

## Estado

App funcional de punta a punta. Pendientes/mejoras: ampliar el catálogo de pesos,
integrar compras reales para reducir el "sin proveedor", calibrar pesos por categoría,
y lead time real por proveedor.
