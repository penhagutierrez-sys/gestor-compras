"""
Ejecuta el motor completo.
Lo usan main.py (terminal) y app.py (la ventana).

Para la ventana, los datos crudos (ventas + stock) se cargan UNA vez con
cargar_crudos() y luego se clasifica por sucursal con clasificar() sin releer
el Excel — así cambiar de sucursal es rápido.
"""
import numpy as np
import pandas as pd

import config
from . import cargar_datos as cd
from . import analisis as an
from . import ordenes as oc


def _aplicar_maestro(res, maestro, prop):
    """
    Aplica el maestro 80/20: ABC oficial (Pareto) y NIVEL de demanda = run-rate anual
    (CANT_ANUAL/12) repartido por la PROPORCIÓN fija de la sucursal ('prop'; 1.0 = todas).
    Conserva la forma/σ escalándola por el mismo factor.
    """
    # INNER: reduce el universo a los SKU del maestro (top-N del 80/20).
    r = res.merge(maestro, on="CODIGO", how="inner")
    r["ABC"] = r["ABC_8020"].where(r["ABC_8020"].notna(), r["ABC"])
    cant = pd.to_numeric(r["CANT_ANUAL"], errors="coerce")
    # nivel mensual base: run-rate 80/20 si existe; si no, el pronóstico ya calculado.
    base = (cant / 12.0).where(cant.notna() & (cant > 0), r["PRONOSTICO_MENSUAL"])
    nuevo = base * prop                      # repartido por la proporción de la sucursal
    factor = (nuevo / r["PRONOSTICO_MENSUAL"].where(r["PRONOSTICO_MENSUAL"] > 0)).fillna(1.0)
    r["SIGMA_MENSUAL"] = r["SIGMA_MENSUAL"].fillna(0.0) * factor
    r["PRONOSTICO_MENSUAL"] = nuevo
    return r.drop(columns=["ABC_8020", "CANT_ANUAL"], errors="ignore")


def cargar_crudos(progreso=None):
    """Lee ventas, stock y proveedores crudos (una sola vez). (df_ventas, stock_raw, prov)."""
    if progreso:
        progreso("Cargando ventas y stock...")
    df = cd.cargar_ventas(config.RUTA_VENTAS, config.HOJA_VENTAS)
    stock_raw = None
    if config.RUTA_STOCK:
        stock_raw = cd.cargar_stock_raw(config.RUTA_STOCK, config.HOJA_STOCK)
    prov = None
    if getattr(config, "RUTA_PROVEEDORES", None):
        try:
            prov = cd.cargar_proveedores(config.RUTA_PROVEEDORES, config.HOJA_PROVEEDORES)
        except Exception:  # noqa: BLE001  (proveedores es opcional)
            prov = None
    maestro = None
    if getattr(config, "RUTA_MAESTRO_8020", None):
        try:
            maestro = cd.cargar_maestro_8020(config.RUTA_MAESTRO_8020, config.HOJA_MAESTRO_8020)
        except Exception:  # noqa: BLE001  (maestro 80/20 es opcional)
            maestro = None
    return df, stock_raw, prov, maestro


def clasificar(df, stock_raw, sucursal=None, maestro=None, progreso=None):
    """
    Clasifica la salud de inventario. Las VENTAS se reparten por PROPORCION_VENTAS (el
    80/20 no viene por sucursal); el INVENTARIO usa el STOCK REAL por sucursal (tiene
    variación por producto -> ventas ≠ inventario, traslados con sentido). 'maestro'
    (80/20) define ABC, nivel de demanda y reduce el universo a sus SKU.
    """
    def avisar(msg):
        if progreso:
            progreso(msg)

    prop_v = float(config.PROPORCION_VENTAS.get(int(sucursal), 0.0)) if sucursal else 1.0

    avisar("Analizando (ABC / XYZ / pronóstico)...")
    res = an.analizar(df)                      # toda la base; la demanda entra por proporción
    if maestro is not None:
        res = _aplicar_maestro(res, maestro, prop_v)
    elif prop_v != 1.0:
        res = res.assign(PRONOSTICO_MENSUAL=res["PRONOSTICO_MENSUAL"] * prop_v,
                         SIGMA_MENSUAL=res["SIGMA_MENSUAL"] * prop_v)

    stock = None
    if stock_raw is not None:
        avisar("Cruzando stock...")
        # Inventario = stock REAL por sucursal (variación por producto -> traslados con sentido).
        sr = stock_raw[stock_raw["SUCURSAL"] == str(sucursal)] if sucursal else stock_raw
        stock = cd.stock_por_codigo(cd.agregar_stock(sr), res)

    avisar("Clasificando salud de inventario...")
    return oc.clasificar_inventario(res, stock=stock)


def ejecutar(progreso=None, sucursal=None):
    """Corre todo el flujo de una (carga + clasifica). Para uso simple/terminal."""
    df, stock_raw, _prov, maestro = cargar_crudos(progreso)
    return clasificar(df, stock_raw, sucursal=sucursal, maestro=maestro, progreso=progreso)
