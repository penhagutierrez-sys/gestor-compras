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

# Stock actual (export de Power BI). Si se deja en None, el motor sugiere
# SOLO por demanda (sin restar stock).
# NOTA: este export trae NOMBRE_PRODUCTO pero no CODIGO -> se cruza por nombre
# (provisional). Lo ideal es re-exportar incluyendo la columna de código.
RUTA_STOCK = r"C:\Users\Thinkpad\Downloads\data (1).xlsx"
HOJA_STOCK = "Export"

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

# Estado de inventario según DÍAS DE COBERTURA = stock / demanda diaria.
# (Práctica estándar de retail: Lowe's, Sodimac, RELEX, Slim4 razonan en
#  días/semanas de cobertura, no en "stock 0" a secas.)
DIAS_CRITICO = 7       # <= 1 semana de cobertura -> reponer urgente
DIAS_BAJO = 30         # <= 1 mes                 -> por reponer
DIAS_SALUDABLE = 90    # <= 3 meses               -> saludable; más = sobrestock

# --- PUNTO DE REORDEN (modelo de nivel de servicio por clase ABC) ---
# ROP = demanda_diaria * lead_time + stock_seguridad
# stock_seguridad = Z * sigma_diaria * sqrt(lead_time)   (King si hubiera sigma de lead time)
Z_POR_CLASE = {"A": 2.05, "B": 1.65, "C": 1.28}   # nivel de servicio 98% / 95% / 90%
LEAD_TIME_GLOBAL_DIAS = 7        # días de entrega del proveedor (SUPUESTO, no es dato real)
LEAD_TIME_POR_RUBRO = {}         # override opcional por categoría, ej: {"FIERRO": 21}
SIGMA_LEAD_TIME_DIAS = 0         # variabilidad del lead time (0 = sin datos de proveedor)
SIGMA_FLOOR_FRAC = 0.5           # piso de la σ diaria como fracción de la demanda diaria
SS_MAX_DIAS = 45                 # techo del stock de seguridad (en días de demanda)
DIAS_OBJETIVO = 30               # cobertura objetivo al reponer (nivel máximo S)

# Carpeta donde se guardan las órdenes generadas.
CARPETA_SALIDAS = Path(__file__).parent / "salidas"
