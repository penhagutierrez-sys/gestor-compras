"""
Clasificación de inventario y órdenes de compra sugeridas.
==========================================================
En vez de una simple "lista de compra", clasificamos CADA producto por su
SALUD DE INVENTARIO, como hacen los líderes de retail (Lowe's, Sodimac) y el
software especializado (RELEX, Slim4). La métrica base es la
DÍAS DE COBERTURA = stock actual / demanda diaria esperada.

Estados:
- QUIEBRE      : sin stock y con demanda (venta perdida ahora).
- CRITICO      : cobertura <= DIAS_CRITICO (reponer urgente).
- BAJO         : cobertura <= DIAS_BAJO (por reponer).
- SALUDABLE    : cobertura en banda objetivo.
- SOBRESTOCK   : cobertura muy alta (capital inmovilizado, no comprar).
- SIN ROTACION : tiene stock pero sin ventas recientes (lento/muerto).
- SIN DATO     : no cruzó con el archivo de stock.
"""
import numpy as np
import pandas as pd

import config


def clasificar_inventario(res, stock=None):
    """Devuelve TODOS los productos relevantes con su estado de salud y cuánto pedir."""
    df = res.copy()

    # --- Stock actual ---
    if stock is not None:
        df = df.merge(stock, on="CODIGO", how="left")
        s = pd.to_numeric(df["STOCK_ACTUAL"], errors="coerce")
        df["STOCK_CONOCIDO"] = s.notna()      # ¿cruzó con el archivo de stock?
        df["STOCK_ACTUAL"] = s.fillna(0.0)
    else:
        df["STOCK_ACTUAL"] = 0.0
        df["STOCK_CONOCIDO"] = False

    # --- Costo unitario estimado y valor del stock (para medir capital) ---
    df["COSTO_UNIT"] = (df["COSTO_TOTAL"] / df["CANTIDAD_TOTAL"]).replace(
        [np.inf, -np.inf], 0).fillna(0)
    df["VALOR_STOCK"] = (df["STOCK_ACTUAL"] * df["COSTO_UNIT"]).round(0)

    # --- Demanda diaria y DÍAS DE COBERTURA (la métrica clave) ---
    df["DEMANDA_DIARIA"] = df["PRONOSTICO_MENSUAL"] / 30.0
    df["COBERTURA_DIAS"] = np.where(
        df["DEMANDA_DIARIA"] > 0, df["STOCK_ACTUAL"] / df["DEMANDA_DIARIA"], np.nan)

    # --- Cuánto pedir = objetivo de cobertura (con colchón XYZ) - stock ---
    factor = df["XYZ"].map(config.FACTOR_SEGURIDAD).fillna(1.0)
    df["DEMANDA_OBJETIVO"] = df["PRONOSTICO_MENSUAL"] * config.MESES_COBERTURA * factor
    sugerido = (df["DEMANDA_OBJETIVO"] - df["STOCK_ACTUAL"]).clip(lower=0)
    df["SUGERIDO_PEDIR"] = np.ceil(sugerido).astype(int)
    df["MONTO_ESTIMADO"] = (df["SUGERIDO_PEDIR"] * df["COSTO_UNIT"]).round(0)

    # --- Estado de salud de inventario ---
    # OJO con el orden: SIN DATO y SIN ROTACION van primero para no confundirlos
    # con un quiebre o un sobrestock.
    cond = [
        ~df["STOCK_CONOCIDO"],                            # no sabemos su stock
        df["DEMANDA_DIARIA"] <= 0,                        # sin ventas recientes
        df["STOCK_ACTUAL"] <= 0,                          # quiebre
        df["COBERTURA_DIAS"] <= config.DIAS_CRITICO,      # crítico
        df["COBERTURA_DIAS"] <= config.DIAS_BAJO,         # bajo
        df["COBERTURA_DIAS"] <= config.DIAS_SALUDABLE,    # saludable
    ]
    estados = ["SIN DATO", "SIN ROTACION", "QUIEBRE", "CRITICO", "BAJO", "SALUDABLE"]
    df["ESTADO"] = np.select(cond, estados, default="SOBRESTOCK")

    # --- Universo relevante: lo que vende, o lo que tiene stock conocido ---
    # (descartamos productos sin demanda y sin stock: no hay nada que decir de ellos).
    universo = (df["PRONOSTICO_MENSUAL"] > 0) | (df["STOCK_CONOCIDO"] & (df["STOCK_ACTUAL"] > 0))
    df = df[universo].copy()

    return df.sort_values("VENTA_TOTAL", ascending=False).reset_index(drop=True)
