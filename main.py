"""
Corre el motor desde la terminal (sin ventana).
Útil para probar rápido. Para la app con ventana usa:  python app.py
"""
import config
from motor import pipeline
from motor import exportar as ex


def main():
    ordenes = pipeline.ejecutar(progreso=lambda m: print(" •", m))
    monto = ordenes["MONTO_ESTIMADO"].sum()
    print(f"\n{len(ordenes):,} productos a pedir | monto estimado: ${monto:,.0f}")
    ruta = ex.exportar_excel(ordenes)
    print(f"Excel generado: {ruta}")


if __name__ == "__main__":
    main()
