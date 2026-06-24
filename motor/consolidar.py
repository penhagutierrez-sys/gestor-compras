"""
Consolidación de las órdenes de compra sugeridas en camiones, por proveedor/origen.
====================================================================================
Honestidad (clave): lo CONFIABLE es agrupar los sugeridos por proveedor/origen y su
MONTO. El PESO es ESTIMADO (solo ~9% de los productos trae peso real en el nombre;
el cemento en saco es el caso preciso). Por eso el nº de camiones es una ESTIMACIÓN
y se rotula como tal en la interfaz, junto con el % de la carga con peso real.
"""
import os
import re
import unicodedata

import numpy as np
import pandas as pd

import config


def cargar_catalogo_pesos():
    """Catálogo CODIGO->peso_kg de búsquedas web (Sodimac/Easy/Construmart). {} si no existe."""
    ruta = getattr(config, "RUTA_CATALOGO_PESOS", None)
    if not ruta or not os.path.exists(ruta):
        return {}
    try:
        c = pd.read_csv(ruta, dtype={"CODIGO": str})
        c = c[pd.to_numeric(c["PESO_KG"], errors="coerce").fillna(0) > 0]
        if "MATCH" in c.columns:   # solo pesos con CALCE EXACTO (no aproximados)
            c = c[c["MATCH"].astype(str).str.strip().str.lower() == "exacta"]
        return dict(zip(c["CODIGO"].astype(str).str.strip(),
                        pd.to_numeric(c["PESO_KG"], errors="coerce")))
    except Exception:  # noqa: BLE001
        return {}

# "(1.120 K)" = 1,120 kg  |  "25 KG" = 25 kg  (convención del maestro de productos)
_PAT_PAR = re.compile(r"\(\s*(\d+[.,]?\d*)\s*K\s*\)")
_PAT_KG = re.compile(r"(\d+[.,]?\d*)\s*KG\b")


def _norm(s):
    """Mayúsculas, sin acentos ni Ñ, sin espacios extremos (para comparar)."""
    s = str(s).upper().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s


def _peso_del_nombre(nombre):
    """Peso (kg) si el nombre lo trae explícito; si no, None."""
    s = str(nombre).upper()
    for pat in (_PAT_PAR, _PAT_KG):
        m = pat.search(s)
        if m:
            try:
                v = float(m.group(1).replace(",", "."))
            except ValueError:
                continue
            if 0 < v <= config.PESO_MAX_PLAUSIBLE_KG:
                return v
    return None


def _origen(proveedor):
    p = _norm(proveedor)
    if p in ("", "NAN", "SIN PROVEEDOR"):
        return "Sin proveedor"
    for kw, org in config.MAPEO_ORIGENES:
        if _norm(kw) in p:
            return org
    return "Otros proveedores"


def consolidar(inv, prov=None):
    """
    Detalle por producto a comprar (SUGERIDO_PEDIR > 0) con proveedor, origen y
    peso estimado. Devuelve un DataFrame listo para agrupar.
    """
    df = inv[inv["SUGERIDO_PEDIR"] > 0].copy()

    if prov is not None and len(df):
        df = df.merge(prov, on="CODIGO", how="left")
    if "PROVEEDOR" not in df.columns:
        df["PROVEEDOR"] = ""
    df["PROVEEDOR"] = df["PROVEEDOR"].fillna("").astype(str).str.strip()
    df.loc[df["PROVEEDOR"].eq("") | df["PROVEEDOR"].str.lower().eq("nan"), "PROVEEDOR"] = "Sin proveedor"
    df["ORIGEN"] = df["PROVEEDOR"].map(_origen)

    # Peso: catálogo web (máx. confianza) -> del nombre (confiable) -> default RUBRO (estimado).
    defaults = {_norm(k): v for k, v in config.PESO_DEFAULT_RUBRO.items()}
    catalogo = cargar_catalogo_pesos()
    pu, conf = [], []
    for codigo, nombre, rubro in zip(df["CODIGO"], df["PRODUCTO"], df["RUBRO"]):
        if codigo in catalogo:
            pu.append(float(catalogo[codigo])); conf.append(True)
            continue
        p = _peso_del_nombre(nombre)
        if p is not None:
            pu.append(p); conf.append(True)
        else:
            pu.append(defaults.get(_norm(rubro), config.PESO_DEFAULT_GLOBAL)); conf.append(False)
    df["PESO_UNIT_EST"] = pu
    df["PESO_CONFIABLE"] = conf
    df["PESO_TOTAL_EST"] = (df["PESO_UNIT_EST"] * df["SUGERIDO_PEDIR"]).round(0)
    df["PESO_CONF_KG"] = np.where(df["PESO_CONFIABLE"], df["PESO_TOTAL_EST"], 0.0)
    return df


def resumen(detalle, por="ORIGEN"):
    """Agrupa por 'ORIGEN' o 'PROVEEDOR' con totales y camiones estimados."""
    if len(detalle) == 0:
        return detalle.iloc[0:0]
    aggs = dict(
        PRODUCTOS=("CODIGO", "nunique"),
        UNIDADES=("SUGERIDO_PEDIR", "sum"),
        MONTO=("MONTO_ESTIMADO", "sum"),
        KG=("PESO_TOTAL_EST", "sum"),
        KG_CONF=("PESO_CONF_KG", "sum"),
    )
    if por == "PROVEEDOR":
        aggs["ORIGEN"] = ("ORIGEN", "first")
    g = detalle.groupby(por).agg(**aggs).reset_index()
    g["CAMIONES"] = np.ceil(g["KG"] / config.CAMION_PAYLOAD_KG).clip(lower=1).astype(int)
    g["PCT_CONF"] = (g["KG_CONF"] / g["KG"].replace(0, np.nan) * 100).fillna(0).round(0).astype(int)
    return g.sort_values("MONTO", ascending=False).reset_index(drop=True)
