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
LEAD_TIME_GLOBAL_DIAS = 7        # días de entrega por defecto (SIMULADO, no es dato real)
# Lead time SIMULADO por categoría (RUBRO): construcción local rápido; importados/eléctrico
# más lento. Son supuestos ajustables hasta tener el lead time real por proveedor.
LEAD_TIME_POR_RUBRO = {
    "MATERIALES DE CONSTRUCCION": 5, "OBRA GRUESA": 5, "ESTRUCTURAS Y TECHOS": 7,
    "REVESTIMIENTO": 7, "REVESTIMIENTOS": 7, "MADERA Y TABLERO": 6,
    "PINTURA": 10, "PINTURAS": 10, "GASFITERIA": 8, "BAÑO Y COCINA": 12,
    "ELECTRICIDAD": 12, "ILUMINACION": 14, "HERRAMIENTAS": 15, "HER. Y FERRETERIA": 12,
    "FERRETERIA": 10, "JARDIN": 10, "CLIMATIZACION": 14, "HOGAR Y TERMINACIONES": 10,
    "OUTDOOR Y CAMPING": 14, "ASEO": 8, "ORGANIZACIÓN": 10, "INSUMOS": 7,
}
SIGMA_LEAD_TIME_DIAS = 0         # variabilidad del lead time (0 = sin datos de proveedor)
SIGMA_FLOOR_FRAC = 0.5           # piso de la σ diaria como fracción de la demanda diaria
SS_MAX_DIAS = 45                 # techo del stock de seguridad (en días de demanda)
DIAS_OBJETIVO = 30               # cobertura objetivo al reponer (nivel máximo S)

# --- CONSOLIDACIÓN EN CAMIÓN (agrupar sugeridos por proveedor/origen) ---
# Maestro de productos con su proveedor (cruza por CODIGO ~83% con ventas).
RUTA_PROVEEDORES = r"C:\Users\Thinkpad\OneDrive - FERRETERIA SOLUCENTER LTDA\Escritorio\Solucenter\Solicitud Foto-Descripción por Producto-Proveedor.xlsx"
HOJA_PROVEEDORES = "Datos Maepro"
# Proveedor (en mayúsculas) que CONTENGA la keyword -> origen. Primer match gana.
MAPEO_ORIGENES = [
    ("CHILEMAT", "Santiago · Chilemat (general)"),
    ("POLPAICO", "Concepción · Cemento"),
    ("BIO BIO", "Concepción · Cemento"),
    ("BIOBIO", "Concepción · Cemento"),
    ("CEMENTO", "Concepción · Cemento"),
    ("MADETALCA", "Los Ángeles · Polines"),
]
# Camión: carga útil legal en Chile (~Decreto 158 MOP, conservador). Igual para ambos
# modelos; FH500 = ruta larga Santiago→Arauco, FM460 = reparto regional/cemento/polines.
CAMION_PAYLOAD_KG = 28000
# Peso estimado por RUBRO (kg/unidad) cuando el nombre NO trae peso. SON SUPUESTOS,
# ajustables; el peso del nombre (ej. "25 KG") siempre manda sobre estos.
PESO_DEFAULT_RUBRO = {
    "MATERIALES DE CONSTRUCCION": 10.0, "OBRA GRUESA": 15.0, "ESTRUCTURAS Y TECHOS": 12.0,
    "REVESTIMIENTO": 8.0, "REVESTIMIENTOS": 8.0, "MADERA Y TABLERO": 10.0,
    "PINTURA": 5.0, "PINTURAS": 5.0, "GASFITERIA": 2.5, "BANO Y COCINA": 4.0,
    "ELECTRICIDAD": 1.0, "ILUMINACION": 1.0, "HERRAMIENTAS": 1.5, "HER. Y FERRETERIA": 1.0,
    "FERRETERIA": 0.5, "JARDIN": 3.0, "CLIMATIZACION": 5.0, "HOGAR Y TERMINACIONES": 2.0,
    "OUTDOOR Y CAMPING": 2.0, "ASEO": 1.5, "ORGANIZACION": 2.0, "INSUMOS": 1.0,
}
PESO_DEFAULT_GLOBAL = 2.0     # kg/unidad si no hay peso ni RUBRO mapeado
PESO_MAX_PLAUSIBLE_KG = 2000  # descarta parseos absurdos del nombre
# Catálogo de pesos obtenidos por búsqueda web (Sodimac/Easy/Construmart). Máxima
# confianza: si un CODIGO está aquí, su peso manda sobre el parseo y los defaults.
RUTA_CATALOGO_PESOS = Path(__file__).parent / "data" / "catalogo_pesos.csv"

# --- MAESTRO 80/20 (Pareto): manda en ABC y en el nivel de demanda (run-rate 12 meses) ---
RUTA_MAESTRO_8020 = Path(__file__).parent / "data" / "80-20.xlsx"
HOJA_MAESTRO_8020 = "BD"
# Como el 80/20 no viene separado por sucursal, la demanda se reparte con esta
# PROPORCIÓN fija por sucursal (código -> fracción; suma = 1.0).
SUCURSAL_PROPORCION = {
    101: 0.22,   # Casa Matriz Arauco
    201: 0.22,   # Sucursal Cañete
    301: 0.20,   # Sucursal Curanilahue
    401: 0.11,   # Bodega O'Higgins
    501: 0.11,   # Bodega Huillinco
    601: 0.14,   # Sucursal Santa Juana
}

# Carpeta donde se guardan las órdenes generadas.
CARPETA_SALIDAS = Path(__file__).parent / "salidas"
