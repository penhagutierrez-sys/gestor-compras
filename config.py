"""
Configuración del Gestor de Compras 2.0
=======================================
Aquí van las RUTAS de tus archivos y los PARÁMETROS del motor.
Es el único lugar que normalmente vas a tocar para ajustar el comportamiento.
"""
from pathlib import Path

# --- Archivos de entrada (ajusta si los mueves de lugar) ---
RUTA_VENTAS = r"C:\Users\Thinkpad\OneDrive - FERRETERIA SOLUCENTER LTDA\Escritorio\BBDD_Ventas_Reclasificada_2026.xlsx"
HOJA_VENTAS = "BD Vta"

# Stock actual: pendiente re-exportar desde Power BI con datos reales.
# Si se deja en None, el motor sugiere SOLO por demanda (sin restar stock).
RUTA_STOCK = None  # ej: r"C:\Users\Thinkpad\Downloads\stock.csv"

# --- Parámetros del motor ---
# Cuántos meses de demanda queremos tener cubiertos en stock.
MESES_COBERTURA = 1

# Colchón de seguridad según qué tan variable es la demanda (clasificación XYZ).
# X = demanda estable, Z = demanda muy errática (necesita más colchón).
FACTOR_SEGURIDAD = {"X": 1.0, "Y": 1.5, "Z": 2.0}

# Cortes para la clasificación ABC (por valor económico acumulado).
# A = hasta el 80% del valor, B = hasta el 95%, C = el resto.
CORTE_A = 0.80
CORTE_B = 0.95

# Carpeta donde se guardan las órdenes generadas.
CARPETA_SALIDAS = Path(__file__).parent / "salidas"
