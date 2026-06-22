"""
Ejecuta el motor completo.
Lo usan main.py (terminal) y app.py (la ventana).

Para la ventana, los datos crudos (ventas + stock) se cargan UNA vez con
cargar_crudos() y luego se clasifica por sucursal con clasificar() sin releer
el Excel — así cambiar de sucursal es rápido.
"""
import config
from . import cargar_datos as cd
from . import analisis as an
from . import ordenes as oc


def cargar_crudos(progreso=None):
    """Lee ventas y stock crudos (una sola vez). Devuelve (df_ventas, stock_raw)."""
    if progreso:
        progreso("Cargando ventas y stock...")
    df = cd.cargar_ventas(config.RUTA_VENTAS, config.HOJA_VENTAS)
    stock_raw = None
    if config.RUTA_STOCK:
        stock_raw = cd.cargar_stock_raw(config.RUTA_STOCK, config.HOJA_STOCK)
    return df, stock_raw


def clasificar(df, stock_raw, sucursal=None, progreso=None):
    """
    Clasifica la salud de inventario. Si 'sucursal' (código, ej. 101) se entrega,
    filtra ventas y stock a esa sucursal; si es None, usa todas (agregado).
    """
    def avisar(msg):
        if progreso:
            progreso(msg)

    if sucursal:
        df = df[df["COD_SUCURSAL"] == sucursal]
        sr = stock_raw[stock_raw["SUCURSAL"] == str(sucursal)] if stock_raw is not None else None
    else:
        sr = stock_raw

    avisar("Analizando (ABC / XYZ / pronóstico)...")
    res = an.analizar(df)

    stock = None
    if sr is not None:
        avisar("Cruzando stock...")
        stock = cd.stock_por_codigo(cd.agregar_stock(sr), res)

    avisar("Clasificando salud de inventario...")
    return oc.clasificar_inventario(res, stock=stock)


def ejecutar(progreso=None, sucursal=None):
    """Corre todo el flujo de una (carga + clasifica). Para uso simple/terminal."""
    df, stock_raw = cargar_crudos(progreso)
    return clasificar(df, stock_raw, sucursal=sucursal, progreso=progreso)
