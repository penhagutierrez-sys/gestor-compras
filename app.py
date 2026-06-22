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


def filtrar(ordenes, modo, texto=""):
    """Aplica el modo elegido y la búsqueda de texto sobre las órdenes."""
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

    texto = (texto or "").strip().upper()
    if texto:
        m2 = (df["PRODUCTO"].astype(str).str.upper().str.contains(texto, regex=False)
              | df["CODIGO"].astype(str).str.upper().str.contains(texto, regex=False))
        df = df[m2]
    return df


# --- La ventana -------------------------------------------------------------
class GestorApp:
    COLS = [
        ("CODIGO", "Código", 110, "w"),
        ("PRODUCTO", "Producto", 320, "w"),
        ("ABC", "ABC", 50, "center"),
        ("URGENCIA", "Estado", 120, "center"),
        ("STOCK_ACTUAL", "Stock", 75, "e"),
        ("PRONOSTICO_MENSUAL", "Pronóstico/mes", 110, "e"),
        ("SUGERIDO_PEDIR", "Sugerido pedir", 110, "e"),
        ("MONTO_ESTIMADO", "Monto estimado", 130, "e"),
    ]

    def __init__(self, root):
        self.root = root
        self.ordenes = None
        self._vista = None

        self._estilos()
        self._barra_marca()
        self._encabezado_pagina()
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
        self.btn_generar = tb.Button(right, text="Actualizar",
                                     bootstyle="secondary-outline", command=self._generar)
        self.btn_generar.pack(side="left", padx=(0, 8))
        self.btn_export = tb.Button(right, text="Exportar a Excel",
                                    bootstyle="primary", command=self._exportar,
                                    state="disabled")
        self.btn_export.pack(side="left")

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
        bar = tb.Frame(self.root, padding=(20, 8))
        bar.pack(fill="x")
        tb.Label(bar, text="Ver", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self.cmb = tb.Combobox(bar, values=MODOS, state="readonly", width=30,
                               bootstyle="primary")
        self.cmb.current(0)
        self.cmb.pack(side="left", padx=(0, 18))
        self.cmb.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtro())

        tb.Label(bar, text="Buscar", bootstyle="secondary").pack(side="left", padx=(0, 6))
        self.busqueda = tb.Entry(bar, width=32)
        self.busqueda.pack(side="left")
        self.busqueda.bind("<KeyRelease>", lambda e: self._aplicar_filtro())

        self.resumen = tb.Label(bar, text="", font=("Segoe UI", 9), bootstyle="secondary")
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
            self.tree.heading(key, text=titulo)
            self.tree.column(key, width=ancho, anchor=anchor, stretch=(key == "PRODUCTO"))
        for key, color in ROW.items():
            self.tree.tag_configure(TAG[key], background=color)
        self.tree.tag_configure("par", background="white")
        self.tree.tag_configure("impar", background="#FAFAFA")

        sb = tb.Scrollbar(card, orient="vertical", command=self.tree.yview,
                          bootstyle="round")
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
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
        self._aplicar_filtro()
        self._status(f"Listo — {len(ordenes):,} productos a pedir en total.")

    def _error(self, msg):
        self.btn_generar.config(state="normal")
        self._status("Error: " + msg)
        Messagebox.show_error(msg, "Error al generar")

    def _aplicar_filtro(self):
        if self.ordenes is None:
            return
        df = filtrar(self.ordenes, self.cmb.get(), self.busqueda.get())
        self._vista = df

        self.tree.delete(*self.tree.get_children())
        for i, (_, fila) in enumerate(df.iterrows()):
            urg = fila["URGENCIA"]
            stock_txt = fmt_num(fila["STOCK_ACTUAL"]) if fila["STOCK_CONOCIDO"] else "?"
            valores = (
                fila["CODIGO"],
                str(fila["PRODUCTO"])[:60],
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
    w, h = 1120, 700
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
