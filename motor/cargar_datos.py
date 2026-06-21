"""
Carga y limpieza de los datos de ventas.
========================================
El Excel de ventas tiene una particularidad: la cantidad y los montos vienen
SEPARADOS en dos columnas, una por año (..._2025 y ..._2026). Nunca vienen las
dos a la vez (si la venta fue en 2025, la de 2026 está en 0 y viceversa).
Aquí las UNIMOS en una sola columna "limpia" para poder trabajar cómodos.
"""
import pandas as pd

# Traducción del nombre del mes (como viene en el Excel) a número de mes.
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Solo cargamos las columnas que el motor necesita (más rápido y liviano).
COLUMNAS = [
    "FECHA_DOC", "Año", "MES", "CODIGO", "PRODUCTO",
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
