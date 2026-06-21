"""
Punto de entrada del motor.
Carga ventas -> analiza (ABC/XYZ/pronóstico) -> genera OCs -> exporta a Excel.
"""
import pandas as pd
import config
from motor import cargar_datos as cd
from motor import analisis as an
from motor import ordenes as oc
from motor import exportar as ex


def main():
    print("1) Cargando ventas... (puede tardar unos segundos)")
    df = cd.cargar_ventas(config.RUTA_VENTAS, config.HOJA_VENTAS)
    print(f"   {len(df):,} filas | {df['CODIGO'].nunique():,} productos.\n")

    print("2) Analizando (ABC / XYZ / pronóstico)...")
    res = an.analizar(df)
    print(f"   {len(res):,} productos analizados.\n")

    print("3) Generando órdenes de compra sugeridas...")
    stock = None  # cuando tengamos el stock real, se carga aquí
    ordenes = oc.generar_ordenes(res, stock=stock)
    monto = ordenes["MONTO_ESTIMADO"].sum()
    print(f"   {len(ordenes):,} productos a pedir | monto estimado: ${monto:,.0f}")
    if stock is None:
        print("   (sin stock todavía: sugerencia por demanda pura)\n")

    print("4) Exportando a Excel...")
    ruta = ex.exportar_excel(ordenes)
    print(f"   Archivo creado: {ruta}\n")

    # Vista rápida de las primeras OCs (clase A).
    print("== Primeras OCs sugeridas (clase A) ==")
    cols = ["CODIGO", "PRODUCTO", "ABC", "XYZ", "SUGERIDO_PEDIR", "MONTO_ESTIMADO"]
    vista = ordenes.head(8)[cols].copy()
    vista["PRODUCTO"] = vista["PRODUCTO"].str.slice(0, 36)
    print(vista.to_string(index=False))


if __name__ == "__main__":
    main()
