"""
GESTOR DE COMPRAS 2.0 — Ventana de escritorio (UI moderna)
==========================================================
Dashboard de SALUD DE INVENTARIO (estilo retail: Lowe's / Sodimac / RELEX / Slim4):
clasifica cada producto por días de cobertura y muestra qué reponer y dónde hay
capital inmovilizado (sobrestock / sin rotación).

Para abrirla:  python app.py   (o doble clic en "Abrir Gestor de Compras.bat")
"""
import os
import threading
import tkinter as tk
from tkinter import ttk

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F401,F403
from ttkbootstrap.dialogs import Messagebox

from motor import pipeline
from motor import exportar as ex

# --- Estados de salud de inventario ---------------------------------------
EST_TXT = {
    "QUIEBRE": "Quiebre", "CRITICO": "Crítico", "BAJO": "Bajo",
    "SALUDABLE": "Saludable", "SOBRESTOCK": "Sobrestock",
    "SIN ROTACION": "Sin rotación", "SIN DATO": "Sin dato",
}
# Tinte de fila por estado (semáforo).
EST_ROW = {
    "QUIEBRE": "#F5B7B1", "CRITICO": "#F8CBA6", "BAJO": "#FBE7A1",
    "SALUDABLE": "#ABEBC6", "SOBRESTOCK": "#AED6F1",
    "SIN ROTACION": "#D5D8DC", "SIN DATO": "#ECECEC",
}
EST_TAG = {e: e.lower().replace(" ", "_") for e in EST_TXT}
# Orden por gravedad para el ordenamiento de la columna Estado.
EST_ORDEN = {"QUIEBRE": 0, "CRITICO": 1, "BAJO": 2, "SIN DATO": 3,
             "SALUDABLE": 4, "SOBRESTOCK": 5, "SIN ROTACION": 6}

# Vistas (modo) -> estados que muestran.
MODOS = [
    "Por reponer (quiebre + crítico + bajo)",
    "Quiebre (sin stock)",
    "Crítico (urgente)",
    "Saludable",
    "Sobrestock (exceso)",
    "Sin rotación (lento)",
    "Sin dato de stock",
    "Todos",
]
ESTADOS_POR_MODO = {
    MODOS[0]: ["QUIEBRE", "CRITICO", "BAJO"],
    MODOS[1]: ["QUIEBRE"],
    MODOS[2]: ["CRITICO"],
    MODOS[3]: ["SALUDABLE"],
    MODOS[4]: ["SOBRESTOCK"],
    MODOS[5]: ["SIN ROTACION"],
    MODOS[6]: ["SIN DATO"],
}

# Semáforo (píldoras): etiqueta, estados que agrupa, color.
SEM_DEFS = [
    ("Quiebre", ["QUIEBRE"], "danger"),
    ("Por reponer", ["CRITICO", "BAJO"], "warning"),
    ("Saludable", ["SALUDABLE"], "success"),
    ("Sobrestock", ["SOBRESTOCK"], "info"),
    ("Sin rotación", ["SIN ROTACION"], "dark"),
    ("Sin dato", ["SIN DATO"], "secondary"),
]

TODAS_FAMILIAS = "Todas las familias"
TODAS_CATEGORIAS = "Todas las categorías"

NAVY = "#032D60"
NAVY_SUB = "#9FB6D6"
CARD_BORDER = "#DDDBDA"


# --- Funciones "puras" (sin ventana), fáciles de probar ---------------------
def fmt_num(v):
    return f"{int(round(float(v))):,}".replace(",", ".")


def fmt_clp(v):
    return "$ " + fmt_num(v)


def fmt_dias(v):
    """Días de cobertura; '—' si no aplica (sin demanda o sin dato)."""
    if v is None or v != v:  # NaN
        return "—"
    return fmt_num(v)


def cap(x):
    """Texto de categoría/familia en formato Título (PINTURA -> Pintura)."""
    s = str(x)
    return "" if s.lower() == "nan" else s.title()


def filtrar(inv, modo, texto="", familia=None, categoria=None):
    """Aplica vista (estado), categoría, familia y búsqueda sobre el inventario."""
    df = inv.sort_values("VENTA_TOTAL", ascending=False)  # más vendidos primero

    estados = ESTADOS_POR_MODO.get(modo)
    if estados:
        df = df[df["ESTADO"].isin(estados)]

    if categoria and categoria != TODAS_CATEGORIAS:
        df = df[df["RUBRO"].astype(str).str.upper() == categoria.upper()]
    if familia and familia != TODAS_FAMILIAS:
        df = df[df["FAMILIA"].astype(str).str.upper() == familia.upper()]

    texto = (texto or "").strip().upper()
    if texto:
        def tiene(col):
            return df[col].astype(str).str.upper().str.contains(texto, regex=False)
        df = df[tiene("PRODUCTO") | tiene("CODIGO") | tiene("RUBRO") | tiene("FAMILIA")]
    return df


# --- La ventana -------------------------------------------------------------
class GestorApp:
    COLS = [
        ("CODIGO", "Código", 105, "w"),
        ("PRODUCTO", "Producto", 230, "w"),
        ("RUBRO", "Categoría", 130, "w"),
        ("FAMILIA", "Familia", 140, "w"),
        ("ABC", "ABC", 46, "center"),
        ("ESTADO", "Estado", 96, "center"),
        ("STOCK_ACTUAL", "Stock", 66, "e"),
        ("COBERTURA_DIAS", "Cobertura (d)", 92, "e"),
        ("SUGERIDO_PEDIR", "Sugerido", 84, "e"),
        ("MONTO_ESTIMADO", "Monto compra", 112, "e"),
    ]

    def __init__(self, root):
        self.root = root
        self.inv = None
        self._vista = None
        self._sort_col = None
        self._sort_asc = True

        self._estilos()
        self._barra_marca()
        self._encabezado_pagina()
        self._kpis()
        self._semaforo()
        self._toolbar()
        self._tarjeta_tabla()
        self._barra_estado()

        self._generar()

    # ---- estilos base ----
    def _estilos(self):
        st = self.root.style
        st.configure("Treeview", rowheight=30, font=("Segoe UI", 10),
                     background="white", fieldbackground="white", borderwidth=0)
        st.configure("Treeview.Heading", font=("Segoe UI Semibold", 10),
                     padding=(10, 10), background="#F3F3F3", foreground="#3E3E3C",
                     relief="flat")
        st.map("Treeview.Heading", background=[("active", "#E9E9E9")])
        st.map("Treeview", background=[("selected", "#D8E6F6")],
               foreground=[("selected", "#161616")])

    def _barra_marca(self):
        bar = tk.Frame(self.root, bg=NAVY, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="Gestor de Compras", bg=NAVY, fg="white",
                 font=("Segoe UI Semibold", 15)).pack(side="left", padx=20)
        tk.Label(bar, text="Salud de inventario · Ferretería Solucenter", bg=NAVY,
                 fg=NAVY_SUB, font=("Segoe UI", 9)).pack(side="left", pady=(6, 0))

    def _encabezado_pagina(self):
        ph = tb.Frame(self.root, padding=(20, 16, 20, 6))
        ph.pack(fill="x")
        left = tb.Frame(ph)
        left.pack(side="left", fill="x", expand=True)
        tb.Label(left, text="Salud de inventario",
                 font=("Segoe UI Semibold", 16)).pack(anchor="w")
        tb.Label(left, text="Qué reponer y dónde hay capital inmovilizado — por días de cobertura",
                 font=("Segoe UI", 9), bootstyle="secondary").pack(anchor="w")
        right = tb.Frame(ph)
        right.pack(side="right")
        self.btn_generar = tb.Button(right, text="↻  Actualizar",
                                     bootstyle="secondary-outline", command=self._generar)
        self.btn_generar.pack(side="left", padx=(0, 8))
        self.btn_export = tb.Button(right, text="↧  Exportar a Excel",
                                    bootstyle="primary", command=self._exportar,
                                    state="disabled")
        self.btn_export.pack(side="left")

    def _kpis(self):
        row = tb.Frame(self.root, padding=(20, 10, 20, 2))
        row.pack(fill="x")
        self.kpi = {}
        defs = [
            ("rep_monto", "Por reponer (compra)", "#C0392B"),
            ("rep_cnt", "Productos por reponer", "#B9770E"),
            ("over", "Capital en sobrestock", "#1F6FB2"),
            ("dead", "Capital sin rotación", "#566573"),
        ]
        for i, (key, label, color) in enumerate(defs):
            card = tk.Frame(row, bg="white", highlightbackground=CARD_BORDER,
                            highlightthickness=1)
            card.pack(side="left", expand=True, fill="x", padx=(0 if i == 0 else 12, 0))
            val = tk.Label(card, text="—", bg="white", fg=color,
                           font=("Segoe UI", 20, "bold"))
            val.pack(anchor="w", padx=16, pady=(12, 0))
            tk.Label(card, text=label, bg="white", fg="#5C5C5C",
                     font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 12))
            self.kpi[key] = val

    def _semaforo(self):
        bar = tb.Frame(self.root, padding=(20, 6))
        bar.pack(fill="x")
        self.sem = {}
        for txt, estados, color in SEM_DEFS:
            pill = tb.Label(bar, text=f"0  ·  {txt}", bootstyle=f"inverse-{color}",
                            font=("Segoe UI Semibold", 10), padding=(12, 6))
            pill.pack(side="left", padx=(0, 10))
            self.sem[txt] = (pill, estados)

    def _toolbar(self):
        wrap = tb.Frame(self.root, padding=(20, 8))
        wrap.pack(fill="x")
        fila1 = tb.Frame(wrap)
        fila1.pack(fill="x")
        tb.Label(fila1, text="Ver", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self.cmb = tb.Combobox(fila1, values=MODOS, state="readonly", width=30,
                               bootstyle="primary")
        self.cmb.current(0)
        self.cmb.pack(side="left", padx=(0, 16))
        self.cmb.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtro())

        tb.Label(fila1, text="Categoría", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self.cmb_categoria = tb.Combobox(fila1, values=[TODAS_CATEGORIAS], state="readonly",
                                         width=22, bootstyle="primary")
        self.cmb_categoria.current(0)
        self.cmb_categoria.pack(side="left", padx=(0, 16))
        self.cmb_categoria.bind("<<ComboboxSelected>>", lambda e: self._cambio_categoria())

        tb.Label(fila1, text="Familia", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self.cmb_familia = tb.Combobox(fila1, values=[TODAS_FAMILIAS], state="readonly",
                                       width=24, bootstyle="primary")
        self.cmb_familia.current(0)
        self.cmb_familia.pack(side="left")
        self.cmb_familia.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtro())

        fila2 = tb.Frame(wrap)
        fila2.pack(fill="x", pady=(8, 0))
        tb.Label(fila2, text="Buscar", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self.busqueda = tb.Entry(fila2, width=40)
        self.busqueda.pack(side="left")
        self.busqueda.bind("<KeyRelease>", lambda e: self._aplicar_filtro())
        self.resumen = tb.Label(fila2, text="", font=("Segoe UI", 9), bootstyle="secondary")
        self.resumen.pack(side="right")

    def _tarjeta_tabla(self):
        outer = tb.Frame(self.root, padding=(20, 6, 20, 16))
        outer.pack(fill="both", expand=True)
        card = tk.Frame(outer, bg="white", highlightbackground=CARD_BORDER,
                        highlightthickness=1)
        card.pack(fill="both", expand=True)

        cols = [c[0] for c in self.COLS]
        self.tree = ttk.Treeview(card, columns=cols, show="headings")
        for key, titulo, ancho, anchor in self.COLS:
            self.tree.heading(key, text=titulo, command=lambda k=key: self._ordenar(k))
            self.tree.column(key, width=ancho, anchor=anchor, stretch=(key == "PRODUCTO"))
        for est, tag in EST_TAG.items():
            self.tree.tag_configure(tag, background=EST_ROW[est])
        self.tree.tag_configure("par", background="white")
        self.tree.tag_configure("impar", background="#FAFAFA")

        sbx = tb.Scrollbar(card, orient="horizontal", command=self.tree.xview,
                           bootstyle="round")
        sbx.pack(side="bottom", fill="x")
        sb = tb.Scrollbar(card, orient="vertical", command=self.tree.yview,
                          bootstyle="round")
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set, xscrollcommand=sbx.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)

    def _barra_estado(self):
        self.estado = tb.Label(self.root, text="", anchor="w", padding=(20, 4),
                               bootstyle="secondary", font=("Segoe UI", 8))
        self.estado.pack(fill="x", side="bottom")

    # ---- lógica ----
    def _status(self, msg):
        self.estado.config(text=msg)

    def _generar(self):
        self.btn_generar.config(state="disabled")
        self.btn_export.config(state="disabled")
        self._status("Procesando… (cargando ventas y stock, ~5 segundos)")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            inv = pipeline.ejecutar(progreso=lambda m: self.root.after(0, self._status, m))
            self.root.after(0, self._listo, inv)
        except Exception as e:  # noqa: BLE001
            self.root.after(0, self._error, str(e))

    def _listo(self, inv):
        self.inv = inv
        self.btn_generar.config(state="normal")
        self.btn_export.config(state="normal")

        vc = inv["ESTADO"].value_counts()
        for txt, (pill, estados) in self.sem.items():
            total = int(sum(vc.get(e, 0) for e in estados))
            pill.config(text=f"{total:,}  ·  {txt}".replace(",", "."))

        rep = inv[inv["ESTADO"].isin(["QUIEBRE", "CRITICO", "BAJO"])]
        over = inv[inv["ESTADO"] == "SOBRESTOCK"]
        dead = inv[inv["ESTADO"] == "SIN ROTACION"]
        self.kpi["rep_monto"].config(text=fmt_clp(rep["MONTO_ESTIMADO"].sum()))
        self.kpi["rep_cnt"].config(text=fmt_num(len(rep)))
        self.kpi["over"].config(text=fmt_clp(over["VALOR_STOCK"].sum()))
        self.kpi["dead"].config(text=fmt_clp(dead["VALOR_STOCK"].sum()))

        cats = sorted({cap(x) for x in inv["RUBRO"].dropna().unique()
                       if str(x).lower() != "nan"})
        self.cmb_categoria["values"] = [TODAS_CATEGORIAS] + cats
        self.cmb_categoria.current(0)
        self.cmb_familia["values"] = [TODAS_FAMILIAS] + self._familias_de(inv)
        self.cmb_familia.current(0)

        self._aplicar_filtro()
        self._status(f"Listo — {len(inv):,} productos clasificados.")

    def _error(self, msg):
        self.btn_generar.config(state="normal")
        self._status("Error: " + msg)
        Messagebox.show_error(msg, "Error al generar")

    def _familias_de(self, df):
        return sorted({cap(x) for x in df["FAMILIA"].dropna().unique()
                       if str(x).lower() != "nan"})

    def _cambio_categoria(self):
        cat = self.cmb_categoria.get()
        if cat and cat != TODAS_CATEGORIAS:
            sub = self.inv[self.inv["RUBRO"].astype(str).str.upper() == cat.upper()]
        else:
            sub = self.inv
        self.cmb_familia["values"] = [TODAS_FAMILIAS] + self._familias_de(sub)
        self.cmb_familia.set(TODAS_FAMILIAS)
        self._aplicar_filtro()

    def _ordenar(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._aplicar_filtro()

    def _ordenar_df(self, df):
        col = self._sort_col
        if not col:
            return df
        if col == "ESTADO":
            clave = df["ESTADO"].map(EST_ORDEN)
            return (df.assign(_k=clave)
                      .sort_values("_k", ascending=self._sort_asc, kind="stable")
                      .drop(columns="_k"))
        return df.sort_values(col, ascending=self._sort_asc, kind="stable")

    def _encabezados(self):
        flecha = " ▲" if self._sort_asc else " ▼"
        for key, titulo, _a, _b in self.COLS:
            self.tree.heading(key, text=titulo + (flecha if key == self._sort_col else ""))

    def _aplicar_filtro(self):
        if self.inv is None:
            return
        df = filtrar(self.inv, self.cmb.get(), self.busqueda.get(),
                     self.cmb_familia.get(), self.cmb_categoria.get())
        df = self._ordenar_df(df)
        self._encabezados()
        self._vista = df

        self.tree.delete(*self.tree.get_children())
        for i, (_, fila) in enumerate(df.iterrows()):
            est = fila["ESTADO"]
            conocido = fila["STOCK_CONOCIDO"]
            stock_txt = fmt_num(fila["STOCK_ACTUAL"]) if conocido else "?"
            cob_txt = fmt_dias(fila["COBERTURA_DIAS"]) if conocido else "—"
            valores = (
                fila["CODIGO"],
                str(fila["PRODUCTO"])[:60],
                cap(fila["RUBRO"]),
                cap(fila["FAMILIA"]),
                fila["ABC"],
                EST_TXT.get(est, est),
                stock_txt,
                cob_txt,
                fmt_num(fila["SUGERIDO_PEDIR"]),
                fmt_clp(fila["MONTO_ESTIMADO"]),
            )
            tag = EST_TAG.get(est, "impar" if i % 2 else "par")
            self.tree.insert("", "end", values=valores, tags=(tag,))

        monto = df["MONTO_ESTIMADO"].sum()
        self.resumen.config(text=f"{len(df):,} productos  ·  compra {fmt_clp(monto)}"
                            .replace(",", "."))

    def _exportar(self):
        if self._vista is None or len(self._vista) == 0:
            Messagebox.show_info("No hay productos en la vista actual.", "Nada que exportar")
            return
        ruta = ex.exportar_excel(self._vista)
        self._status(f"Exportado: {ruta}")
        if Messagebox.yesno(f"Se generó el archivo:\n\n{ruta}\n\n¿Abrirlo ahora?",
                            "Exportado") == "Yes":
            try:
                os.startfile(ruta)
            except Exception:  # noqa: BLE001
                pass


def main():
    root = tb.Window(themename="cosmo", title="Gestor de Compras 2.0")
    GestorApp(root)
    root.update_idletasks()
    w, h = 1240, 770
    x = max(0, (root.winfo_screenwidth() - w) // 2)
    y = max(0, (root.winfo_screenheight() - h) // 3)
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.lift()
    root.attributes("-topmost", True)
    root.after(900, lambda: root.attributes("-topmost", False))
    root.focus_force()
    root.mainloop()


if __name__ == "__main__":
    main()
