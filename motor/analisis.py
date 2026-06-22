"""
El "cerebro" del motor: ABC, XYZ y pronóstico de demanda.
=========================================================
- ABC: clasifica por VALOR económico (regla de Pareto 80/15/5).
- XYZ: clasifica por ESTABILIDAD de la demanda (qué tan parejo se vende).
- Pronóstico: cuánto esperamos vender el próximo mes (media móvil reciente).
La combinación ABC + XYZ es la "matriz de decisión" (AX, AZ, CZ, etc.).
"""
import numpy as np
import pandas as pd
import config


def quitar_no_productos(df):
    """
    Saca líneas que NO son productos comprables (rebates, servicios, etc.).
    En esta base esas líneas empiezan con código 'ZZ'. Así no sugerimos
    'comprar' un rebate o un flete.
    """
    es_ruido = df["CODIGO"].astype(str).str.upper().str.startswith("ZZ")
    return df[~es_ruido].copy()


def tabla_productos(df):
    """Una fila por producto con su descripción y totales acumulados."""
    return (
        df.groupby("CODIGO")
        .agg(
            PRODUCTO=("PRODUCTO", "first"),
            RUBRO=("RUBRO", "first"),
            FAMILIA=("FAMILIA", "first"),
            MARCA=("MARCA", "first"),
            VENTA_TOTAL=("VENTA", "sum"),
            COSTO_TOTAL=("COSTO", "sum"),
            CANTIDAD_TOTAL=("CANTIDAD", "sum"),
        )
        .reset_index()
    )


def clasificar_abc(prod):
    """
    A / B / C según el valor económico (VENTA) acumulado.
    A = los pocos productos que concentran la mayor parte de la venta.
    """
    prod = prod.sort_values("VENTA_TOTAL", ascending=False).copy()
    total = prod["VENTA_TOTAL"].sum()
    prod["%_ACUM"] = prod["VENTA_TOTAL"].cumsum() / total if total else 0
    prod["ABC"] = np.where(
        prod["%_ACUM"] <= config.CORTE_A, "A",
        np.where(prod["%_ACUM"] <= config.CORTE_B, "B", "C"),
    )
    return prod


def matriz_mensual(df):
    """
    Tabla: filas = producto, columnas = (año, mes), valores = cantidad vendida.
    Los meses sin venta quedan en 0 (importante para medir variabilidad).
    """
    return df.pivot_table(
        index="CODIGO", columns=["Año", "MES_NUM"],
        values="CANTIDAD", aggfunc="sum", fill_value=0,
    )


def clasificar_xyz(piv):
    """
    X / Y / Z según el coeficiente de variación (CV = desviación / promedio).
    X = demanda estable (fácil de pronosticar), Z = demanda errática.
    """
    media = piv.mean(axis=1)
    desv = piv.std(axis=1)
    cv = (desv / media).replace([np.inf, -np.inf], np.nan).fillna(0)
    xyz = np.where(cv <= 0.5, "X", np.where(cv <= 1.0, "Y", "Z"))
    return pd.DataFrame({"CV": cv, "XYZ": xyz}, index=piv.index)


def pronostico(piv):
    """
    Pronóstico de demanda mensual = promedio de los últimos 3 meses disponibles
    de 2026 (media móvil corta). También entrega la tendencia 2025 -> 2026.
    """
    cols_2026 = sorted(c for c in piv.columns if c[0] == 2026)
    cols_2025 = sorted(c for c in piv.columns if c[0] == 2025)
    cero = pd.Series(0.0, index=piv.index)

    ult3 = cols_2026[-3:]
    prom_3m = piv[ult3].mean(axis=1) if ult3 else cero
    prom_2026 = piv[cols_2026].mean(axis=1) if cols_2026 else cero
    tot_2025 = piv[cols_2025].sum(axis=1) if cols_2025 else cero
    tot_2026 = piv[cols_2026].sum(axis=1) if cols_2026 else cero
    tendencia = tot_2026 / tot_2025.replace(0, np.nan)  # NaN si no vendía en 2025

    # Desviación estándar de la demanda mensual (solo 2026, para no inflarla con
    # los ceros del otro año). Es la base del stock de seguridad del punto de reorden.
    sigma = piv[cols_2026].std(axis=1) if len(cols_2026) >= 2 else cero

    return pd.DataFrame({
        "PRONOSTICO_MENSUAL": prom_3m,
        "PROM_MENSUAL_2026": prom_2026,
        "TENDENCIA_25_26": tendencia,
        "SIGMA_MENSUAL": sigma,
    })


def analizar(df):
    """Orquesta todo: limpia, clasifica ABC y XYZ, y pronostica. Una fila por producto."""
    df = quitar_no_productos(df)
    prod = clasificar_abc(tabla_productos(df)).set_index("CODIGO")
    piv = matriz_mensual(df)
    res = prod.join(clasificar_xyz(piv)).join(pronostico(piv))
    return res.reset_index()
