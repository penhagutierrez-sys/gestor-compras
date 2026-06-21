"""
Punto de entrada del motor (versión de prueba).
Por ahora solo CARGA los datos y muestra un resumen, para verificar que todo
lee bien. En los siguientes pasos le sumamos ABC/XYZ, pronóstico y las OCs.
"""
import config
from motor import cargar_datos as cd


def main():
    print("Cargando ventas... (puede tardar unos segundos)\n")
    df = cd.cargar_ventas(config.RUTA_VENTAS, config.HOJA_VENTAS)

    print(f"OK - {len(df):,} filas  |  {df['CODIGO'].nunique():,} productos distintos")
    meses = sorted(int(m) for m in df["MES_NUM"].dropna().unique())
    print(f"Años: {sorted(df['Año'].dropna().unique())}  |  Meses presentes: {meses}")

    resumen = cd.resumen_mensual(df)

    # Como ejemplo, mostramos el producto que más vendió (en $) y su demanda mensual.
    ventas_por_prod = df.groupby("CODIGO")["VENTA"].sum()
    top = ventas_por_prod.idxmax()
    nombre = df.loc[df["CODIGO"] == top, "PRODUCTO"].iloc[0]
    print(f"\nEjemplo — producto top en ventas: {top}  {nombre}")
    print("Demanda mensual (unidades):")
    print(resumen[resumen["CODIGO"] == top].to_string(index=False))


if __name__ == "__main__":
    main()
