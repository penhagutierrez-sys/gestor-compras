"""
Sugerencia de TRASLADOS ENTRE SUCURSALES.
=========================================
Antes de comprar, conviene mover lo que sobra de una sucursal a otra que lo necesita.
- DONANTE: sucursal donde el producto está SOBRESTOCK (stock por sobre su nivel máximo S)
  o SIN ROTACIÓN (no se vende ahí → todo su stock es excedente).
- RECEPTOR: sucursal donde el producto está bajo su punto de reorden (QUIEBRE/CRÍTICO/BAJO).
Se asigna el excedente a la necesidad (greedy: del mayor excedente a la mayor necesidad).
Solo participan sucursales con dato de stock.
"""
import pandas as pd

from . import pipeline


def sugerir_traslados(df, stock_raw, sucursales):
    """
    df, stock_raw: datos crudos cacheados. sucursales: lista de (cod, nombre).
    Devuelve DataFrame [CODIGO, PRODUCTO, RUBRO, DESDE, HACIA, UNIDADES, VALOR].
    """
    if stock_raw is None:
        return pd.DataFrame()
    con_stock = set(stock_raw["SUCURSAL"].astype(str).str.strip().unique())

    tablas, nombre = {}, {}
    for cod, nom in sucursales:
        if str(cod).strip() not in con_stock:
            continue
        inv = pipeline.clasificar(df, stock_raw, sucursal=cod)
        inv = inv[inv["STOCK_CONOCIDO"]]
        if len(inv):
            tablas[cod] = inv.set_index("CODIGO")
            nombre[cod] = nom
    if len(tablas) < 2:
        return pd.DataFrame()

    codigos = set().union(*[set(t.index) for t in tablas.values()])
    filas = []
    for codigo in codigos:
        donantes, receptores = [], []
        prod = rubro = None
        costo = 0.0
        for cod, t in tablas.items():
            if codigo not in t.index:
                continue
            r = t.loc[codigo]
            prod, rubro, costo = r["PRODUCTO"], r["RUBRO"], float(r["COSTO_UNIT"])
            estado = r["ESTADO"]
            stock = float(r["STOCK_ACTUAL"])
            nivel = float(r["NIVEL_MAX_S"])
            if estado == "SOBRESTOCK":
                surplus = max(0.0, stock - nivel)   # deja al donante en su nivel máximo
                if surplus >= 1:
                    donantes.append([cod, surplus])
            elif estado == "SIN ROTACION":
                if stock >= 1:
                    donantes.append([cod, stock])   # no rota ahí: todo es excedente
            elif estado in ("QUIEBRE", "CRITICO", "BAJO"):
                need = max(0.0, nivel - stock)
                if need >= 1:
                    receptores.append([cod, need])

        if not donantes or not receptores:
            continue
        donantes.sort(key=lambda x: -x[1])
        receptores.sort(key=lambda x: -x[1])
        i = j = 0
        while i < len(donantes) and j < len(receptores):
            mov = int(min(donantes[i][1], receptores[j][1]))
            if mov >= 1:
                filas.append({
                    "CODIGO": codigo, "PRODUCTO": prod, "RUBRO": rubro,
                    "DESDE": nombre[donantes[i][0]], "HACIA": nombre[receptores[j][0]],
                    "UNIDADES": mov, "VALOR": round(mov * costo, 0),
                })
            donantes[i][1] -= mov
            receptores[j][1] -= mov
            if donantes[i][1] < 1:
                i += 1
            if receptores[j][1] < 1:
                j += 1

    if not filas:
        return pd.DataFrame(columns=["CODIGO", "PRODUCTO", "RUBRO", "DESDE", "HACIA", "UNIDADES", "VALOR"])
    return pd.DataFrame(filas).sort_values("VALOR", ascending=False).reset_index(drop=True)
