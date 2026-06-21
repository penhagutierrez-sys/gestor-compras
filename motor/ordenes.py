"""
Genera las Órdenes de Compra sugeridas.
=======================================
Fórmula de cuánto pedir, por producto:

    objetivo  = pronóstico_mensual  x  meses_cobertura  x  factor_seguridad(XYZ)
    sugerido  = objetivo  -  stock_actual      (nunca menos de 0)

- El factor de seguridad da más colchón a los productos de demanda errática (Z).
- Si todavía no tenemos stock, se asume 0 (sugerencia por demanda pura).
"""
import numpy as np
import pandas as pd

import config


def generar_ordenes(res, stock=None):
    """Devuelve solo los productos donde HAY que pedir algo, con su monto estimado."""
    df = res.copy()

    # Stock actual (0 si todavía no lo tenemos). 'stock' es un DataFrame [CODIGO, STOCK_ACTUAL].
    if stock is not None:
        df = df.merge(stock, on="CODIGO", how="left")
        s = pd.to_numeric(df["STOCK_ACTUAL"], errors="coerce")
        df["STOCK_CONOCIDO"] = s.notna()      # ¿este producto cruzó con el archivo de stock?
        df["STOCK_ACTUAL"] = s.fillna(0.0)
    else:
        df["STOCK_ACTUAL"] = 0.0
        df["STOCK_CONOCIDO"] = False

    # Colchón de seguridad según variabilidad (X=1.0, Y=1.5, Z=2.0).
    factor = df["XYZ"].map(config.FACTOR_SEGURIDAD).fillna(1.0)

    # Costo unitario estimado = costo total / unidades vendidas (para valorizar la OC).
    df["COSTO_UNIT"] = (df["COSTO_TOTAL"] / df["CANTIDAD_TOTAL"]).replace(
        [np.inf, -np.inf], 0
    ).fillna(0)

    # Cuánto pedir.
    df["DEMANDA_OBJETIVO"] = df["PRONOSTICO_MENSUAL"] * config.MESES_COBERTURA * factor
    sugerido = (df["DEMANDA_OBJETIVO"] - df["STOCK_ACTUAL"]).clip(lower=0)
    df["SUGERIDO_PEDIR"] = np.ceil(sugerido).astype(int)

    # Monto estimado de la compra.
    df["MONTO_ESTIMADO"] = (df["SUGERIDO_PEDIR"] * df["COSTO_UNIT"]).round(0)

    # --- Urgencia de reposición (lo que el usuario quiere priorizar) ---
    # Cuántos meses de demanda alcanza a cubrir el stock que tenemos hoy.
    df["COBERTURA_MESES"] = np.where(
        df["PRONOSTICO_MENSUAL"] > 0,
        df["STOCK_ACTUAL"] / df["PRONOSTICO_MENSUAL"],
        np.nan,
    )
    # OJO: "SIN DATO" va primero para no confundir stock desconocido con quiebre real.
    condiciones = [
        ~df["STOCK_CONOCIDO"],                               # no sabemos su stock
        df["STOCK_ACTUAL"] <= 0,                             # quiebre total
        df["COBERTURA_MESES"] < config.UMBRAL_COBERTURA,     # por agotarse
    ]
    df["URGENCIA"] = np.select(
        condiciones, ["SIN DATO", "QUIEBRE", "POR AGOTARSE"], default="OK"
    )

    # Solo dejamos los productos con algo que pedir, ordenados por importancia.
    ordenes = df[df["SUGERIDO_PEDIR"] > 0].copy()
    ordenes = ordenes.sort_values(
        ["ABC", "MONTO_ESTIMADO"], ascending=[True, False]
    ).reset_index(drop=True)
    return ordenes
