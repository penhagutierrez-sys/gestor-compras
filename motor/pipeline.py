"""
Ejecuta el motor completo de una sola llamada.
Lo usan tanto main.py (terminal) como app.py (la ventana).
"""
import config
from . import cargar_datos as cd
from . import analisis as an
from . import ordenes as oc


def ejecutar(progreso=None):
    """
    Corre todo el flujo: ventas -> análisis -> stock -> órdenes de compra.
    'progreso' es una función opcional para avisar en qué paso vamos
    (se usa para mostrar mensajes en la ventana).
    Devuelve el DataFrame de órdenes sugeridas.
    """
    def avisar(msg):
        if progreso:
            progreso(msg)

    avisar("Cargando ventas...")
    df = cd.cargar_ventas(config.RUTA_VENTAS, config.HOJA_VENTAS)

    avisar("Analizando (ABC / XYZ / pronóstico)...")
    res = an.analizar(df)

    stock = None
    if config.RUTA_STOCK:
        avisar("Cargando stock...")
        stock_nombre = cd.cargar_stock(config.RUTA_STOCK, config.HOJA_STOCK)
        stock = cd.stock_por_codigo(stock_nombre, res)
        n = int(stock["STOCK_ACTUAL"].notna().sum())
        avisar(f"Stock cruzado: {n:,}/{len(stock):,} productos ({n/len(stock)*100:.0f}%)")

    avisar("Clasificando salud de inventario...")
    inventario = oc.clasificar_inventario(res, stock=stock)
    return inventario
