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
    r = res.merge(maestro, on="CODIGO", how="left")
    r["ABC"] = r["ABC_8020"].where(r["ABC_8020"].notna(), r["ABC"])
    cant = pd.to_numeric(r["CANT_ANUAL"], errors="coerce").fillna(0.0)
    nuevo = (cant / 12.0) * prop
    usar = cant > 0
    factor = (nuevo / r["PRONOSTICO_MENSUAL"].where(r["PRONOSTICO_MENSUAL"] > 0)).fillna(1.0)
    r.loc[usar, "SIGMA_MENSUAL"] = r.loc[usar, "SIGMA_MENSUAL"].fillna(0.0) * factor[usar]
    r.loc[usar, "PRONOSTICO_MENSUAL"] = nuevo[usar]
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
    Clasifica la salud de inventario. Si 'sucursal' (código, ej. 101) se entrega,
    filtra ventas y stock a esa sucursal; si es None, usa todas (agregado).
    'maestro' (80/20) define el ABC oficial y el nivel de demanda.
    """
    def avisar(msg):
        if progreso:
            progreso(msg)

    # Proporción de demanda de la sucursal (el 80/20 no viene separado por sucursal).
    prop = float(config.SUCURSAL_PROPORCION.get(int(sucursal), 0.0)) if sucursal else 1.0

    if sucursal:
        df = df[df["COD_SUCURSAL"] == sucursal]
        sr = stock_raw[stock_raw["SUCURSAL"] == str(sucursal)] if stock_raw is not None else None
    else:
        sr = stock_raw

    avisar("Analizando (ABC / XYZ / pronóstico)...")
    res = an.analizar(df)
    if maestro is not None:
        res = _aplicar_maestro(res, maestro, prop)

    stock = None
    if sr is not None:
        avisar("Cruzando stock...")
        stock = cd.stock_por_codigo(cd.agregar_stock(sr), res)

    avisar("Clasificando salud de inventario...")
    return oc.clasificar_inventario(res, stock=stock)


def ejecutar(progreso=None, sucursal=None):
    """Corre todo el flujo de una (carga + clasifica). Para uso simple/terminal."""
    df, stock_raw, _prov, maestro = cargar_crudos(progreso)
    return clasificar(df, stock_raw, sucursal=sucursal, maestro=maestro, progreso=progreso)
