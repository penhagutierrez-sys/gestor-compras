"""
GESTOR DE COMPRAS 2.0 — Ventana de escritorio (UI moderna)
==========================================================
Interfaz estilo enterprise (inspirada en Salesforce Lightning) construida con
ttkbootstrap: barra de marca, encabezado de página, semáforo de estado con
píldoras, y una tabla de datos limpia dentro de una tarjeta.

Para abrirla:  python app.py   (o doble clic en "Abrir Gestor de Compras.bat")
"""
import os
import threading
import tkinter as tk
from tkinter import ttk

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F401,F403  (LEFT, RIGHT, X, BOTH, ...)
from ttkbootstrap.dialogs import Messagebox

from motor import pipeline
from motor import exportar as ex

# Modos de filtro (el primero es el que se muestra al abrir).
MODOS = [
    "Reponer ya (stock 0 o por agotarse)",
    "Solo quiebre (stock 0)",
    "Top 50 más vendidos",
    "Clase A",
    "Sin dato de stock",
    "Todos",
]

# Texto del estado (el color va en la píldora y el fondo de la fila).
URG_TXT = {
    "QUIEBRE": "Quiebre",
    "POR AGOTARSE": "Por agotarse",
    "SIN DATO": "Sin dato",
    "OK": "Cubierto",
}
# Estilo de color (semántica de ttkbootstrap) por estado.
PILL = {"QUIEBRE": "danger", "POR AGOTARSE": "warning", "OK": "success", "SIN DATO": "secondary"}
# Tinte suave de fila por estado.
ROW = {"QUIEBRE": "#FDE7E9", "POR AGOTARSE": "#FEF3E8", "OK": "#EBF7ED", "SIN DATO": "#F4F4F5"}
TAG = {"QUIEBRE": "quiebre", "POR AGOTARSE": "agotarse", "OK": "ok", "SIN DATO": "sindato"}

# Paleta de la barra de marca (azul Salesforce).
NAVY = "#032D60"
NAVY_SUB = "#9FB6D6"
CARD_BORDER = "#DDDBDA"


# --- Funciones "puras" (sin ventana), fáciles de probar ---------------------
def fmt_num(v):
    """123456.7 -> '123.457' (formato chileno, separador de miles con punto)."""
    return f"{int(round(float(v))):,}".replace(",", ".")


def fmt_clp(v):
    return "$ " + fmt_num(v)


def cap(x):
    """Texto de categoría/familia en formato Título (PINTURA -> Pintura)."""
    s = str(x)
    return "" if s.lower() == "nan" else s.title()


TODAS_FAMILIAS = "Todas las familias"
TODAS_CATEGORIAS = "Todas las categorías"


def filtrar(ordenes, modo, texto="", familia=None, categoria=None):
    """Aplica el modo, la categoría, la familia y la búsqueda sobre las órdenes."""
    df = ordenes.sort_values("VENTA_TOTAL", ascending=False)  # más vendidos primero
    m = modo.lower()

    if modo.startswith("Reponer"):
        df = df[df["URGENCIA"].isin(["QUIEBRE", "POR AGOTARSE"])]
    elif "quiebre" in m:
        df = df[df["URGENCIA"] == "QUIEBRE"]
    elif "sin dato" in m:
        df = df[df["URGENCIA"] == "SIN DATO"]
    elif modo.startswith("Top"):
        n = int("".join(c for c in modo if c.isdigit()))
        df = df.head(n)
    elif modo.startswith("Clase"):
        df = df[df["ABC"] == modo.strip()[-1]]
    # "Todos": no se filtra nada

    # Filtros en cascada: categoría y familia (desplegables de arriba).
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
        ("PRODUCTO", "Producto", 240, "w"),
        ("RUBRO", "Categoría", 140, "w"),
        ("FAMILIA", "Familia", 150, "w"),
        ("ABC", "ABC", 48, "center"),
        ("URGENCIA", "Estado", 110, "center"),
        ("STOCK_ACTUAL", "Stock", 70, "e"),
        ("PRONOSTICO_MENSUAL", "Pronóstico/mes", 105, "e"),
        ("SUGERIDO_PEDIR", "Sugerido pedir", 105, "e"),
        ("MONTO_ESTIMADO", "Monto estimado", 125, "e"),
    ]

    def __init__(self, root):
        self.root = root
        self.ordenes = None
        self._vista = None
        self._sort_col = None     # columna por la que se ordena (None = por venta)
        self._sort_asc = True     # ascendente / descendente

        self._estilos()
        self._barra_marca()
        self._encabezado_pagina()
        self._kpis()
        self._semaforo()
        self._toolbar()
        self._tarjeta_tabla()
        self._barra_estado()

        self._generar()  # carga los datos en segundo plano al abrir

    # ---- estilos base ----
    def _estilos(self):
        st = self.root.style
        st.configure("Treeview", rowheight=30, font=("Segoe UI", 10),
                     background="white", fieldbackground="white", borderwidth=0)
        st.configure("Treeview.Heading", font=("Segoe UI Semibold", 10),
                     padding=(10, 10), background="#F3F3F3", foreground="#3E3E3C",
                     relief="flat")
        st.map("Treeview.Heading", background=[("active", "#E9E9E9")])
        st.map("Treeview",
               background=[("selected", "#D8E6F6")],
               foreground=[("selected", "#161616")])

    # ---- barra de marca (azul) ----
    def _barra_marca(self):
        bar = tk.Frame(self.root, bg=NAVY, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="Gestor de Compras", bg=NAVY, fg="white",
                 font=("Segoe UI Semibold", 15)).pack(side="left", padx=20)
        tk.Label(bar, text="Abastecimiento · Ferretería Solucenter", bg=NAVY,
                 fg=NAVY_SUB, font=("Segoe UI", 9)).pack(side="left", pady=(6, 0))

    # ---- encabezado de página (título + acciones) ----
    def _encabezado_pagina(self):
        ph = tb.Frame(self.root, padding=(20, 16, 20, 6))
        ph.pack(fill="x")
        left = tb.Frame(ph)
        left.pack(side="left", fill="x", expand=True)
        tb.Label(left, text="Productos a reponer",
                 font=("Segoe UI Semibold", 16)).pack(anchor="w")
        tb.Label(left, text="Sugerencias de compra priorizadas por urgencia y rotación",
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

    # ---- KPIs grandes (tarjetas de métricas) ----
    def _kpis(self):
        row = tb.Frame(self.root, padding=(20, 10, 20, 2))
        row.pack(fill="x")
        self.kpi = {}
        defs = [
            ("urg_monto", "Urgente a reponer", "#C0392B"),
            ("urg_cnt", "Productos urgentes", "#B9770E"),
            ("tot_monto", "Inversión total sugerida", "#0B5CAB"),
            ("tot_cnt", "Productos con orden", "#3E3E3C"),
        ]
        for i, (key, label, color) in enumerate(defs):
            card = tk.Frame(row, bg="white", highlightbackground=CARD_BORDER,
                            highlightthickness=1)
            card.pack(side="left", expand=True, fill="x", padx=(0 if i == 0 else 12, 0))
            val = tk.Label(card, text="—", bg="white", fg=color,
                           font=("Segoe UI", 22, "bold"))
            val.pack(anchor="w", padx=16, pady=(12, 0))
            tk.Label(card, text=label, bg="white", fg="#5C5C5C",
                     font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 12))
            self.kpi[key] = val

    # ---- semáforo (píldoras de estado) ----
    def _semaforo(self):
        bar = tb.Frame(self.root, padding=(20, 6))
        bar.pack(fill="x")
        self.sem = {}
        etiquetas = (("QUIEBRE", "En quiebre"), ("POR AGOTARSE", "Por agotarse"),
                     ("OK", "Cubiertos"), ("SIN DATO", "Sin dato"))
        for key, txt in etiquetas:
            pill = tb.Label(bar, text=f"0  ·  {txt}", bootstyle=f"inverse-{PILL[key]}",
                            font=("Segoe UI Semibold", 10), padding=(12, 6))
            pill.pack(side="left", padx=(0, 10))
            self.sem[key] = (pill, txt)

    # ---- toolbar (filtro + búsqueda + contador) ----
    def _toolbar(self):
        wrap = tb.Frame(self.root, padding=(20, 8))
        wrap.pack(fill="x")

        # Fila 1: filtros (Ver + Familia).
        fila1 = tb.Frame(wrap)
        fila1.pack(fill="x")
        tb.Label(fila1, text="Ver", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self.cmb = tb.Combobox(fila1, values=MODOS, state="readonly", width=24,
                               bootstyle="primary")
        self.cmb.current(0)
        self.cmb.pack(side="left", padx=(0, 16))
        self.cmb.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtro())

        tb.Label(fila1, text="Categoría", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self.cmb_categoria = tb.Combobox(fila1, values=[TODAS_CATEGORIAS], state="readonly",
                                         width=24, bootstyle="primary")
        self.cmb_categoria.current(0)
        self.cmb_categoria.pack(side="left", padx=(0, 16))
        self.cmb_categoria.bind("<<ComboboxSelected>>", lambda e: self._cambio_categoria())

        tb.Label(fila1, text="Familia", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self.cmb_familia = tb.Combobox(fila1, values=[TODAS_FAMILIAS], state="readonly",
                                       width=26, bootstyle="primary")
        self.cmb_familia.current(0)
        self.cmb_familia.pack(side="left")
        self.cmb_familia.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtro())

        # Fila 2: búsqueda + contador.
        fila2 = tb.Frame(wrap)
        fila2.pack(fill="x", pady=(8, 0))
        tb.Label(fila2, text="Buscar", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self.busqueda = tb.Entry(fila2, width=40)
        self.busqueda.pack(side="left")
        self.busqueda.bind("<KeyRelease>", lambda e: self._aplicar_filtro())

        self.resumen = tb.Label(fila2, text="", font=("Segoe UI", 9), bootstyle="secondary")
        self.resumen.pack(side="right")

    # ---- tarjeta con la tabla ----
    def _tarjeta_tabla(self):
        outer = tb.Frame(self.root, padding=(20, 6, 20, 16))
        outer.pack(fill="both", expand=True)
        card = tk.Frame(outer, bg="white", highlightbackground=CARD_BORDER,
                        highlightthickness=1)
        card.pack(fill="both", expand=True)

        cols = [c[0] for c in self.COLS]
        self.tree = ttk.Treeview(card, columns=cols, show="headings")
        for key, titulo, ancho, anchor in self.COLS:
            # Clic en el encabezado = ordenar por esa columna.
            self.tree.heading(key, text=titulo, command=lambda k=key: self._ordenar(k))
            self.tree.column(key, width=ancho, anchor=anchor, stretch=(key == "PRODUCTO"))
        for key, color in ROW.items():
            self.tree.tag_configure(TAG[key], background=color)
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

    # ---- barra de estado ----
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
            ordenes = pipeline.ejecutar(
                progreso=lambda m: self.root.after(0, self._status, m))
            self.root.after(0, self._listo, ordenes)
        except Exception as e:  # noqa: BLE001
            self.root.after(0, self._error, str(e))

    def _listo(self, ordenes):
        self.ordenes = ordenes
        self.btn_generar.config(state="normal")
        self.btn_export.config(state="normal")
        vc = ordenes["URGENCIA"].value_counts()
        for key, (pill, txt) in self.sem.items():
            pill.config(text=f"{int(vc.get(key, 0)):,}  ·  {txt}")
        # KPIs grandes.
        urg = ordenes[ordenes["URGENCIA"].isin(["QUIEBRE", "POR AGOTARSE"])]
        self.kpi["urg_monto"].config(text=fmt_clp(urg["MONTO_ESTIMADO"].sum()))
        self.kpi["urg_cnt"].config(text=fmt_num(len(urg)))
        self.kpi["tot_monto"].config(text=fmt_clp(ordenes["MONTO_ESTIMADO"].sum()))
        self.kpi["tot_cnt"].config(text=fmt_num(len(ordenes)))
        # Poblar los desplegables de categoría y familia con lo presente en los datos.
        cats = sorted({cap(x) for x in ordenes["RUBRO"].dropna().unique()
                       if str(x).lower() != "nan"})
        self.cmb_categoria["values"] = [TODAS_CATEGORIAS] + cats
        self.cmb_categoria.current(0)
        self.cmb_familia["values"] = [TODAS_FAMILIAS] + self._familias_de(ordenes)
        self.cmb_familia.current(0)
        self._aplicar_filtro()
        self._status(f"Listo — {len(ordenes):,} productos a pedir en total.")

    def _error(self, msg):
        self.btn_generar.config(state="normal")
        self._status("Error: " + msg)
        Messagebox.show_error(msg, "Error al generar")

    def _ordenar(self, col):
        """Clic en encabezado: ordena por esa columna; segundo clic invierte."""
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._aplicar_filtro()

    def _ordenar_df(self, df):
        """Ordena por la columna elegida usando el VALOR real (no el texto)."""
        col = self._sort_col
        if not col:
            return df  # sin orden manual: queda el de filtrar() (más vendidos)
        if col == "URGENCIA":
            # Orden por gravedad, no alfabético.
            orden = {"QUIEBRE": 0, "POR AGOTARSE": 1, "SIN DATO": 2, "OK": 3}
            clave = df["URGENCIA"].map(orden)
            return (df.assign(_k=clave)
                      .sort_values("_k", ascending=self._sort_asc, kind="stable")
                      .drop(columns="_k"))
        return df.sort_values(col, ascending=self._sort_asc, kind="stable")

    def _encabezados(self):
        """Pone la flecha ▲/▼ en la columna por la que se está ordenando."""
        flecha = " ▲" if self._sort_asc else " ▼"
        for key, titulo, _a, _b in self.COLS:
            self.tree.heading(key, text=titulo + (flecha if key == self._sort_col else ""))

    def _familias_de(self, df):
        """Lista de familias (en formato Título) presentes en un DataFrame."""
        return sorted({cap(x) for x in df["FAMILIA"].dropna().unique()
                       if str(x).lower() != "nan"})

    def _cambio_categoria(self):
        """Al cambiar la categoría, reduce las familias a las de esa categoría."""
        cat = self.cmb_categoria.get()
        if cat and cat != TODAS_CATEGORIAS:
            sub = self.ordenes[self.ordenes["RUBRO"].astype(str).str.upper() == cat.upper()]
        else:
            sub = self.ordenes
        self.cmb_familia["values"] = [TODAS_FAMILIAS] + self._familias_de(sub)
        self.cmb_familia.set(TODAS_FAMILIAS)
        self._aplicar_filtro()

    def _aplicar_filtro(self):
        if self.ordenes is None:
            return
        df = filtrar(self.ordenes, self.cmb.get(), self.busqueda.get(),
                     self.cmb_familia.get(), self.cmb_categoria.get())
        df = self._ordenar_df(df)
        self._encabezados()
        self._vista = df

        self.tree.delete(*self.tree.get_children())
        for i, (_, fila) in enumerate(df.iterrows()):
            urg = fila["URGENCIA"]
            stock_txt = fmt_num(fila["STOCK_ACTUAL"]) if fila["STOCK_CONOCIDO"] else "?"
            valores = (
                fila["CODIGO"],
                str(fila["PRODUCTO"])[:60],
                cap(fila["RUBRO"]),
                cap(fila["FAMILIA"]),
                fila["ABC"],
                URG_TXT.get(urg, urg),
                stock_txt,
                fmt_num(fila["PRONOSTICO_MENSUAL"]),
                fmt_num(fila["SUGERIDO_PEDIR"]),
                fmt_clp(fila["MONTO_ESTIMADO"]),
            )
            tag = TAG.get(urg, "impar" if i % 2 else "par")
            self.tree.insert("", "end", values=valores, tags=(tag,))

        monto = df["MONTO_ESTIMADO"].sum()
        self.resumen.config(text=f"{len(df):,} productos  ·  {fmt_clp(monto)}")

    def _exportar(self):
        if self._vista is None or len(self._vista) == 0:
            Messagebox.show_info("No hay productos en la vista actual.", "Nada que exportar")
            return
        ruta = ex.exportar_excel(self._vista)
        self._status(f"Exportado: {ruta}")
        resp = Messagebox.yesno(f"Se generó el archivo:\n\n{ruta}\n\n¿Abrirlo ahora?",
                                "Exportado")
        if resp == "Yes":
            try:
                os.startfile(ruta)  # abre el Excel (Windows)
            except Exception:  # noqa: BLE001
                pass


def main():
    root = tb.Window(themename="cosmo", title="Gestor de Compras 2.0")
    GestorApp(root)

    # Centrar y traer al frente.
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
