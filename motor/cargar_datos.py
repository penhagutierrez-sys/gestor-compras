"""
Carga y limpieza de los datos de ventas.
========================================
El Excel de ventas tiene una particularidad: la cantidad y los montos vienen
SEPARADOS en dos columnas, una por año (..._2025 y ..._2026). Nunca vienen las
dos a la vez (si la venta fue en 2025, la de 2026 está en 0 y viceversa).
Aquí las UNIMOS en una sola columna "limpia" para poder trabajar cómodos.
"""
import os
import re
import shutil
import tempfile

import numpy as np
import pandas as pd


def _leer_excel_robusto(ruta, hoja, header=0):
    """Lee un Excel; si está bloqueado (abierto en Excel/OneDrive), lo copia a temp y lee la copia."""
    try:
        return pd.read_excel(ruta, sheet_name=hoja, header=header)
    except PermissionError:
        tmp = os.path.join(tempfile.gettempdir(), "gc_" + os.path.basename(str(ruta)))
        shutil.copy2(ruta, tmp)
        return pd.read_excel(tmp, sheet_name=hoja, header=header)

# Traducción del nombre del mes (como viene en el Excel) a número de mes.
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Solo cargamos las columnas que el motor necesita (más rápido y liviano).
COLUMNAS = [
    "FECHA_DOC", "Año", "MES", "COD_SUCURSAL", "SUCURSAL", "CODIGO", "PRODUCTO",
    "RUBRO", "SUPERFAMILIA", "FAMILIA", "MARCA",
    "CANTIDAD_2025", "CANTIDAD_2026",
    "VENTA_2025", "VENTA_2026",
    "COSTO_2025", "COSTO_2026",
    "ABC",
]


def cargar_ventas(ruta, hoja="BD Vta"):
    """Lee el Excel de ventas y devuelve una tabla limpia, lista para analizar."""
    df = pd.read_excel(ruta, sheet_name=hoja, usecols=COLUMNAS)

    # Unimos los dos años en una sola columna (una de las dos siempre es 0).
    df["CANTIDAD"] = df["CANTIDAD_2025"].fillna(0) + df["CANTIDAD_2026"].fillna(0)
    df["VENTA"] = df["VENTA_2025"].fillna(0) + df["VENTA_2026"].fillna(0)
    df["COSTO"] = df["COSTO_2025"].fillna(0) + df["COSTO_2026"].fillna(0)

    # Pasamos el nombre del mes a número (enero -> 1) para poder ordenar/calcular.
    df["MES_NUM"] = df["MES"].astype(str).str.strip().str.lower().map(MESES)

    return df


def resumen_mensual(df):
    """
    Suma la cantidad vendida por producto y por (año, mes).
    Es la base para calcular medias móviles y tendencias.
    """
    g = (
        df.groupby(["CODIGO", "Año", "MES_NUM"])["CANTIDAD"]
        .sum()
        .reset_index()
        .rename(columns={"CANTIDAD": "CANTIDAD_MES"})
    )
    return g


# ---------------------------------------------------------------------------
# STOCK
# ---------------------------------------------------------------------------
def _normalizar_nombre(s):
    """Deja el nombre 'parejo' para poder compararlo: mayúsculas, sin espacios dobles."""
    s = str(s).strip().upper()
    return re.sub(r"\s+", " ", s)


def cargar_stock_raw(ruta, hoja="Export"):
    """
    Lee el export de stock de Power BI (filas por bodega/sucursal) y lo deja limpio:
    quita los subtotales ("Total") y agrega SUCURSAL + nombre normalizado.
    Conserva la sucursal para poder filtrar por ella.
    """
    s = pd.read_excel(ruta, sheet_name=hoja)
    s = s[s["NOMBRE_PRODUCTO"].notna()]
    s = s[~s["NOMBRE_PRODUCTO"].astype(str).str.strip().str.lower().eq("total")]
    s["STOCK_FISICO"] = pd.to_numeric(s["STOCK_FISICO"], errors="coerce").fillna(0)
    s["NOMBRE_NORM"] = s["NOMBRE_PRODUCTO"].map(_normalizar_nombre)
    s["SUCURSAL"] = s["SUCURSAL"].astype(str).str.strip()
    return s[["SUCURSAL", "NOMBRE_NORM", "STOCK_FISICO"]]


def agregar_stock(raw):
    """Suma el stock por producto (nombre). OJO: el export no trae CODIGO."""
    return (
        raw.groupby("NOMBRE_NORM")["STOCK_FISICO"]
        .sum()
        .rename("STOCK_ACTUAL")
        .reset_index()
    )


def cargar_stock(ruta, hoja="Export"):
    """Stock total por producto (todas las sucursales)."""
    return agregar_stock(cargar_stock_raw(ruta, hoja))


def cargar_maestro_8020(ruta, hoja="BD"):
    """
    Maestro Pareto 80/20 (hoja 'BD', encabezado en la fila 2): SKU, CANTIDAD_VENDIDA
    (run-rate anual), PCT_ACUMULADO. Devuelve [CODIGO, CANT_ANUAL, ABC_8020].
    El ABC sale del corte Pareto oficial (A<=80% acumulado, B<=95%, C el resto).
    """
    import config
    df = _leer_excel_robusto(ruta, hoja, header=1)
    df = df.rename(columns={"SKU": "CODIGO", "CANTIDAD_VENDIDA": "CANT_ANUAL"})
    df["CODIGO"] = df["CODIGO"].astype(str).str.strip()
    df = df[df["CODIGO"].ne("") & df["CODIGO"].str.lower().ne("nan")]
    df["CANT_ANUAL"] = pd.to_numeric(df["CANT_ANUAL"], errors="coerce").fillna(0)
    pct = pd.to_numeric(df["PCT_ACUMULADO"], errors="coerce").fillna(1.0)
    df["ABC_8020"] = np.where(pct <= config.CORTE_A, "A",
                              np.where(pct <= config.CORTE_B, "B", "C"))
    df = df.drop_duplicates("CODIGO").sort_values("CANT_ANUAL", ascending=False)
    top = getattr(config, "MAX_SKU", None)
    if top:                                  # solo los top-N SKU (los relevantes del 80/20)
        df = df.head(int(top))
    return df[["CODIGO", "CANT_ANUAL", "ABC_8020"]]


def cargar_proveedores(ruta, hoja="Datos Maepro"):
    """
    Maestro de productos -> proveedor (hoja 'Datos Maepro'). Devuelve [CODIGO, PROVEEDOR].
    Cruza por CODIGO con las ventas (~83%). El proveedor en blanco queda como "".
    """
    p = pd.read_excel(ruta, sheet_name=hoja, dtype=str)
    p = p.rename(columns={"NOMBRE PROVEEDOR": "PROVEEDOR"})
    p["CODIGO"] = p["CODIGO"].astype(str).str.strip()
    p["PROVEEDOR"] = (p["PROVEEDOR"].fillna("").astype(str).str.strip()
                      .replace({"nan": "", "NAN": ""}))
    p = p[p["CODIGO"].ne("") & p["CODIGO"].str.lower().ne("nan")]
    return p.drop_duplicates("CODIGO")[["CODIGO", "PROVEEDOR"]]


def stock_por_codigo(stock_nombre, productos):
    """
    Convierte el stock-por-nombre en stock-por-CODIGO, usando la tabla de
    productos (que sí tiene CODIGO y PRODUCTO) como 'puente'.
    Devuelve un DataFrame [CODIGO, STOCK_ACTUAL] (NaN donde no se encontró nombre).
    """
    p = productos[["CODIGO", "PRODUCTO"]].copy()
    p["NOMBRE_NORM"] = p["PRODUCTO"].map(_normalizar_nombre)
    cruce = p.merge(stock_nombre, on="NOMBRE_NORM", how="left")
    return cruce[["CODIGO", "STOCK_ACTUAL"]]
