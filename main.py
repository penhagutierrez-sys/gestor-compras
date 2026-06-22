"""
Corre el motor desde la terminal (sin ventana).
Útil para probar rápido. Para la app con ventana usa:  python app.py
"""
import config
from motor import pipeline
from motor import exportar as ex


def main():
    inv = pipeline.ejecutar(progreso=lambda m: print(" •", m))
    print("\nEstado de inventario:")
    print(inv["ESTADO"].value_counts().to_string())
    reponer = inv[inv["ESTADO"].isin(["QUIEBRE", "CRITICO", "BAJO"])]
    monto = reponer["MONTO_ESTIMADO"].sum()
    print(f"\nPor reponer: {len(reponer):,} productos | compra estimada: ${monto:,.0f}")
    ruta = ex.exportar_excel(reponer)
    print(f"Excel generado: {ruta}")


if __name__ == "__main__":
    main()
