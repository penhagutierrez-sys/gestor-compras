"""
GESTOR DE COMPRAS 2.0 — Consola de salud de inventario (UI estilo Salesforce Lightning)
=======================================================================================
Layout tipo "console": barra de marca + rail lateral de navegación por estado
(clic = filtra la tabla) + contenido en una grilla maestra de 12 columnas
(medidores KPI, barra de salud, toolbar y tabla). Resuelve la desalineación
usando grid() en vez de pack() para los bloques estructurales.

Para abrirla:  python app.py   (o doble clic en "Abrir Gestor de Compras.bat")
"""
import os
import threading
import tkinter as tk
from tkinter import ttk

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F401,F403
from ttkbootstrap.dialogs import Messagebox

import config
from motor import pipeline
from motor import exportar as ex

# --- Estados ---------------------------------------------------------------
EST_TXT = {
    "QUIEBRE": "Quiebre", "CRITICO": "Crítico", "BAJO": "Bajo",
    "SALUDABLE": "Saludable", "SOBRESTOCK": "Sobrestock",
    "SIN ROTACION": "Sin rotación", "SIN DATO": "-",
}
# Color fuerte por estado (rail, barra de salud).
STATE_COLOR = {
    "QUIEBRE": "#E74C3C", "CRITICO": "#E67E22", "BAJO": "#F1C40F",
    "SALUDABLE": "#27AE60", "SOBRESTOCK": "#3498DB",
    "SIN ROTACION": "#7F8C8D", "SIN DATO": "#BDC3C7",
}
# Tinte suave por estado (fondo de fila en la tabla).
EST_ROW = {
    "QUIEBRE": "#FDEDEC", "CRITICO": "#FDF2E9", "BAJO": "#FEF9E7",
    "SALUDABLE": "#EAFAF1", "SOBRESTOCK": "#EBF5FB",
    "SIN ROTACION": "#F2F3F4", "SIN DATO": "#F8F9F9",
}
EST_TAG = {e: e.lower().replace(" ", "_") for e in EST_TXT}
EST_ORDEN = {"QUIEBRE": 0, "CRITICO": 1, "BAJO": 2, "SIN DATO": 3,
             "SALUDABLE": 4, "SOBRESTOCK": 5, "SIN ROTACION": 6}
# Orden de los segmentos en la barra de salud.
BARRA_ORDEN = ["QUIEBRE", "CRITICO", "BAJO", "SALUDABLE", "SOBRESTOCK",
               "SIN ROTACION", "SIN DATO"]

# Items del rail lateral: (etiqueta, estados que agrupa [None=todos], color de acento).
RAIL_ITEMS = [
    ("Por reponer", ["QUIEBRE", "CRITICO", "BAJO"], "#E67E22"),
    ("Quiebre", ["QUIEBRE"], "#E74C3C"),
    ("Crítico", ["CRITICO"], "#E67E22"),
    ("Bajo", ["BAJO"], "#F1C40F"),
    ("Saludable", ["SALUDABLE"], "#27AE60"),
    ("Sobrestock", ["SOBRESTOCK"], "#3498DB"),
    ("Sin rotación", ["SIN ROTACION"], "#7F8C8D"),
    ("Sin dato", ["SIN DATO"], "#BDC3C7"),
    ("Todos", None, "#5C5C5C"),
]

TODAS_FAMILIAS = "Todas las familias"
TODAS_CATEGORIAS = "Todas las categorías"

# --- Marca / paleta: verde + naranja como ACENTO, fondo BLANCO, líneas gris pizarra (Danish) ---
FONT = "Inter"
FONT_SEMI = "Inter SemiBold"
GREEN = "#2E5E3A"      # acento primario
ORANGE = "#C75B1E"
INK = "#1F2933"        # texto principal (gris pizarra oscuro)
SLATE = "#64748B"      # texto secundario
LINE = "#E2E8F0"       # hairlines gris pizarra, sutiles
PALETA = {
    "primary": "#2E5E3A", "secondary": "#64748B", "success": "#3A7D4E",
    "info": "#5E8C7B", "warning": "#C75B1E", "danger": "#B23B2E",
    "light": "#FFFFFF", "dark": INK, "bg": "#FFFFFF", "fg": INK,
    "selectbg": "#2E5E3A", "selectfg": "#FFFFFF", "border": LINE,
    "inputfg": INK, "inputbg": "#FFFFFF", "active": "#F1F5F9",
}
CARD_BORDER = LINE
RAIL_BG = "#FFFFFF"
RAIL_SEL = "#F1F5F9"    # selección sutil (gris pizarra muy claro)
GUTTER = 14
PAD = 22


def _aplicar_tema(root):
    """Registra y activa el tema de marca (verde/naranja, fondo claro) + fuente Inter."""
    import tkinter.font as tkfont
    from ttkbootstrap.style import ThemeDefinition
    root.style.register_theme(ThemeDefinition("solucenter", PALETA, "light"))
    root.style.theme_use("solucenter")
    for nm in ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont", "TkTooltipFont"):
        try:
            tkfont.nametofont(nm).configure(family=FONT)
        except tk.TclError:
            pass


# --- Funciones puras --------------------------------------------------------
def fmt_num(v):
    return f"{int(round(float(v))):,}".replace(",", ".")


def fmt_clp(v):
    return "$ " + fmt_num(v)


def fmt_millones(v):
    return f"$ {v / 1e6:,.1f}M".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_dias(v):
    if v is None or v != v:  # NaN
        return "—"
    return fmt_num(v)


def cap(x):
    s = str(x)
    return "" if s.lower() == "nan" else s.title()


def filtrar(inv, estados, texto="", familia=None, categoria=None):
    """Filtra el inventario por estados (lista o None=todos), categoría, familia y texto."""
    df = inv.sort_values("VENTA_TOTAL", ascending=False)
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
        ("PRODUCTO", "Producto", 250, "w"),
        ("RUBRO", "Categoría", 130, "w"),
        ("FAMILIA", "Familia", 140, "w"),
        ("ABC", "ABC", 46, "center"),
        ("ESTADO", "Estado", 96, "center"),
        ("STOCK_ACTUAL", "Stock", 66, "e"),
        ("COBERTURA_DIAS", "Cobertura (d)", 92, "e"),
        ("PUNTO_REORDEN", "Pto. reorden", 96, "e"),
        ("SUGERIDO_PEDIR", "Sugerido", 84, "e"),
        ("MONTO_ESTIMADO", "Monto compra", 112, "e"),
    ]
    # KPI: clave, etiqueta, estilo, es_porcentaje
    KPIS = [
        ("inmovil", "Inmovilizado", "danger", True),
        ("reponer", "Por reponer", "success", False),
        ("sobre", "Sobrestock", "warning", True),
        ("dead", "Sin rotación", "secondary", True),
    ]

    def __init__(self, root):
        self.root = root
        self.inv = None
        self._vista = None
        self._sort_col = None
        self._sort_asc = True
        self._estados_activos = ["QUIEBRE", "CRITICO", "BAJO"]  # vista inicial

        self._estilos()
        self._barra_marca()
        self._barra_estado()          # abajo (pack), antes del shell
        self._shell()                 # rail + main
        self._generar()

    # ---- estilos ----
    def _estilos(self):
        st = self.root.style
        st.configure("Treeview", rowheight=30, font=(FONT, 10),
                     background="white", fieldbackground="white", borderwidth=0)
        st.configure("Treeview.Heading", font=(FONT_SEMI, 10),
                     padding=(10, 10), background="#F8FAFC", foreground=INK, relief="flat")
        st.map("Treeview.Heading", background=[("active", "#F1F5F9")])
        st.map("Treeview", background=[("selected", "#EAF1EC")],
               foreground=[("selected", INK)])

    def _barra_marca(self):
        bar = tk.Frame(self.root, bg="#FFFFFF", height=58)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=GREEN, width=4, height=26).pack(side="left", padx=(PAD, 12), pady=16)
        tk.Label(bar, text="Gestor de Compras", bg="#FFFFFF", fg=INK,
                 font=(FONT_SEMI, 15)).pack(side="left", pady=(15, 0))
        tk.Label(bar, text="Salud de inventario · Ferretería Solucenter", bg="#FFFFFF",
                 fg=SLATE, font=(FONT, 9)).pack(side="left", padx=(12, 0), pady=(21, 0))
        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x", side="top")  # hairline

    def _barra_estado(self):
        self.estado = tb.Label(self.root, text="", anchor="w", padding=(PAD, 4),
                               bootstyle="secondary", font=(FONT, 8))
        self.estado.pack(fill="x", side="bottom")

    # ---- shell: rail (izq) + main (der) ----
    def _shell(self):
        shell = tb.Frame(self.root)
        shell.pack(fill="both", expand=True, side="top")
        shell.columnconfigure(0, weight=0, minsize=236)
        shell.columnconfigure(1, weight=0)   # hairline vertical
        shell.columnconfigure(2, weight=1)
        shell.rowconfigure(0, weight=1)
        self._rail(shell)
        tk.Frame(shell, bg=LINE, width=1).grid(row=0, column=1, sticky="ns")
        self._main(shell)

    def _rail(self, shell):
        rail = tk.Frame(shell, bg=RAIL_BG)
        rail.grid(row=0, column=0, sticky="nsew")
        tk.Label(rail, text="ESTADO DE INVENTARIO", bg=RAIL_BG, fg=SLATE,
                 font=(FONT_SEMI, 8)).pack(anchor="w", padx=16, pady=(14, 6))

        self._rail_items = {}
        for label, estados, color in RAIL_ITEMS:
            it = tk.Frame(rail, bg=RAIL_BG, cursor="hand2")
            it.pack(fill="x")
            acc = tk.Frame(it, bg=RAIL_BG, width=4)        # barra de acento (se pinta al seleccionar)
            acc.pack(side="left", fill="y")
            inner = tk.Frame(it, bg=RAIL_BG)
            inner.pack(side="left", fill="x", expand=True, padx=(10, 12), pady=6)
            dot = tk.Label(inner, text="●", bg=RAIL_BG, fg=color, font=(FONT, 9))
            dot.pack(side="left", padx=(0, 8))
            lbl = tk.Label(inner, text=label, bg=RAIL_BG, fg=INK,
                           anchor="w", font=(FONT, 10))
            lbl.pack(side="left")
            cnt = tk.Label(inner, text="0", bg=RAIL_BG, fg=SLATE,
                           font=(FONT_SEMI, 9))
            cnt.pack(side="right")
            for w in (it, inner, dot, lbl, cnt):
                w.bind("<Button-1>", lambda e, es=estados, lb=label: self._drill(es, lb))
            self._rail_items[label] = {"frame": it, "acc": acc, "cnt": cnt,
                                       "estados": estados, "color": color,
                                       "widgets": (it, inner, dot, lbl, cnt)}

        # Bloque inferior: capital inmovilizado.
        sep = tk.Frame(rail, bg=LINE, height=1)
        sep.pack(fill="x", padx=12, pady=(12, 0))
        cap_box = tk.Frame(rail, bg=RAIL_BG)
        cap_box.pack(fill="x", side="bottom", padx=16, pady=14)
        tk.Label(cap_box, text="CAPITAL INMOVILIZADO", bg=RAIL_BG, fg=SLATE,
                 font=(FONT_SEMI, 8)).pack(anchor="w", pady=(0, 4))
        self.lbl_cap_sobre = tk.Label(cap_box, text="Sobrestock  —", bg=RAIL_BG,
                                      fg=INK, font=(FONT, 9), anchor="w")
        self.lbl_cap_sobre.pack(anchor="w")
        self.lbl_cap_dead = tk.Label(cap_box, text="Sin rotación  —", bg=RAIL_BG,
                                     fg=INK, font=(FONT, 9), anchor="w")
        self.lbl_cap_dead.pack(anchor="w")

    def _main(self, shell):
        main = tb.Frame(shell, padding=(PAD, 14, PAD, 14))
        main.grid(row=0, column=2, sticky="nsew")
        for c in range(12):
            main.columnconfigure(c, weight=1, uniform="g")
        main.rowconfigure(4, weight=1)  # la tabla crece
        self.main = main

        # Fila 0: encabezado de página + acciones.
        head = tb.Frame(main)
        head.grid(row=0, column=0, columnspan=12, sticky="ew", pady=(0, 10))
        head.columnconfigure(0, weight=1)
        izq = tb.Frame(head)
        izq.grid(row=0, column=0, sticky="w")
        tb.Label(izq, text="Salud de inventario",
                 font=(FONT_SEMI, 16)).pack(anchor="w")
        tb.Label(izq, text=f"Punto de reorden y cobertura · lead time {config.LEAD_TIME_GLOBAL_DIAS} días (supuesto, configurable)",
                 font=(FONT, 9), bootstyle="secondary").pack(anchor="w")
        der = tb.Frame(head)
        der.grid(row=0, column=1, sticky="e")
        self.btn_generar = tb.Button(der, text="↻  Actualizar",
                                     bootstyle="secondary-outline", command=self._generar)
        self.btn_generar.pack(side="left", padx=(0, 8))
        self.btn_export = tb.Button(der, text="↧  Exportar a Excel",
                                    bootstyle="primary", command=self._exportar, state="disabled")
        self.btn_export.pack(side="left")

        # Fila 1: 4 medidores KPI (columnspan=3 cada uno).
        self.kpi = {}
        for i, (key, label, style, espct) in enumerate(self.KPIS):
            cell = tb.Frame(main)
            cell.grid(row=1, column=i * 3, columnspan=3, sticky="nsew",
                      padx=(0 if i == 0 else GUTTER, 0), pady=(0, 8))
            meter = tb.Meter(cell, metersize=128, amountused=0, amounttotal=100,
                             subtext=label, bootstyle=style,
                             textright="%" if espct else "", stripethickness=8,
                             subtextfont=(FONT, 9))
            meter.pack()
            det = tk.Label(cell, text="—", fg="#5C5C5C", font=(FONT_SEMI, 10))
            det.pack()
            self.kpi[key] = {"meter": meter, "det": det, "pct": espct}

        # Fila 2: barra 100% apilada del mix de salud + leyenda.
        self._barra_salud(main)

        # Fila 3: toolbar (categoría + familia | buscar + contador).
        self._toolbar(main)

        # Fila 4: tabla.
        self._tabla(main)

    def _barra_salud(self, main):
        wrap = tb.Frame(main)
        wrap.grid(row=2, column=0, columnspan=12, sticky="ew", pady=(0, 8))
        cont = tk.Frame(wrap, bg="white", height=22, highlightbackground=CARD_BORDER,
                        highlightthickness=1)
        cont.pack(fill="x")
        cont.pack_propagate(False)
        self._barra_cont = cont
        self._barra_segs = {}
        for est in BARRA_ORDEN:
            seg = tk.Frame(cont, bg=STATE_COLOR[est])
            self._barra_segs[est] = seg
        leg = tb.Frame(wrap)
        leg.pack(fill="x", pady=(4, 0))
        for est in BARRA_ORDEN:
            chip = tk.Frame(leg, bg="white")
            chip.pack(side="left", padx=(0, 14))
            tk.Label(chip, text="■", fg=STATE_COLOR[est], bg="white",
                     font=(FONT, 9)).pack(side="left")
            tk.Label(chip, text=EST_TXT[est] if est != "SIN DATO" else "Sin dato",
                     fg="#5C5C5C", bg="white", font=(FONT, 8)).pack(side="left")

    def _toolbar(self, main):
        bar = tb.Frame(main)
        bar.grid(row=3, column=0, columnspan=12, sticky="ew", pady=(2, 8))
        bar.columnconfigure(4, weight=1)  # espaciador
        tb.Label(bar, text="Categoría", bootstyle="secondary").grid(row=0, column=0, padx=(0, 6))
        self.cmb_categoria = tb.Combobox(bar, values=[TODAS_CATEGORIAS], state="readonly",
                                         width=22, bootstyle="primary")
        self.cmb_categoria.current(0)
        self.cmb_categoria.grid(row=0, column=1, padx=(0, 16))
        self.cmb_categoria.bind("<<ComboboxSelected>>", lambda e: self._cambio_categoria())
        tb.Label(bar, text="Familia", bootstyle="secondary").grid(row=0, column=2, padx=(0, 6))
        self.cmb_familia = tb.Combobox(bar, values=[TODAS_FAMILIAS], state="readonly",
                                       width=24, bootstyle="primary")
        self.cmb_familia.current(0)
        self.cmb_familia.grid(row=0, column=3, sticky="w")
        self.cmb_familia.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtro())

        self.busqueda = tb.Entry(bar, width=26)
        self.busqueda.grid(row=0, column=5, sticky="e", padx=(0, 10))
        self.busqueda.bind("<KeyRelease>", lambda e: self._aplicar_filtro())
        self.resumen = tb.Label(bar, text="", font=(FONT, 9), bootstyle="secondary")
        self.resumen.grid(row=0, column=6, sticky="e")

    def _tabla(self, main):
        card = tk.Frame(main, bg="white", highlightbackground=CARD_BORDER, highlightthickness=1)
        card.grid(row=4, column=0, columnspan=12, sticky="nsew")
        cols = [c[0] for c in self.COLS]
        self.tree = ttk.Treeview(card, columns=cols, show="headings")
        for key, titulo, ancho, anchor in self.COLS:
            self.tree.heading(key, text=titulo, command=lambda k=key: self._ordenar(k))
            self.tree.column(key, width=ancho, anchor=anchor, stretch=(key == "PRODUCTO"))
        for est, tag in EST_TAG.items():
            self.tree.tag_configure(tag, background=EST_ROW[est])
        self.tree.tag_configure("par", background="white")
        self.tree.tag_configure("impar", background="#FAFAFA")
        sbx = tb.Scrollbar(card, orient="horizontal", command=self.tree.xview, bootstyle="round")
        sbx.pack(side="bottom", fill="x")
        sb = tb.Scrollbar(card, orient="vertical", command=self.tree.yview, bootstyle="round")
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set, xscrollcommand=sbx.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)

    # ---- carga ----
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
        cats = sorted({cap(x) for x in inv["RUBRO"].dropna().unique() if str(x).lower() != "nan"})
        self.cmb_categoria["values"] = [TODAS_CATEGORIAS] + cats
        self.cmb_categoria.current(0)
        self.cmb_familia["values"] = [TODAS_FAMILIAS] + self._familias_de(inv)
        self.cmb_familia.current(0)
        # Abre mostrando el panorama global; al seleccionar un estado, todo se recalcula.
        self._drill(None, "Todos")
        self._status(f"Listo — {len(inv):,} productos clasificados.".replace(",", "."))

    def _actualizar_rail(self, scope):
        """Contadores del rail según categoría/familia/búsqueda (faceta, todos los estados)."""
        vc = scope["ESTADO"].value_counts()
        for label, info in self._rail_items.items():
            est = info["estados"]
            total = len(scope) if est is None else int(sum(vc.get(e, 0) for e in est))
            info["cnt"].config(text=fmt_num(total))

    def _actualizar_metricas(self, df):
        """KPIs (medidores), barra de salud y capital — recalculados para la VISTA actual."""
        vc = df["ESTADO"].value_counts()
        cap_total = float(df["VALOR_STOCK"].sum()) or 1.0
        val_sobre = float(df.loc[df["ESTADO"] == "SOBRESTOCK", "VALOR_STOCK"].sum())
        val_dead = float(df.loc[df["ESTADO"] == "SIN ROTACION", "VALOR_STOCK"].sum())
        self.lbl_cap_sobre.config(text=f"Sobrestock   {fmt_millones(val_sobre)}")
        self.lbl_cap_dead.config(text=f"Sin rotación   {fmt_millones(val_dead)}")
        rep = df[df["ESTADO"].isin(["QUIEBRE", "CRITICO", "BAJO"])]
        self._set_kpi("inmovil", round((val_sobre + val_dead) / cap_total * 100),
                      fmt_millones(val_sobre + val_dead))
        self._set_kpi("reponer", len(rep),
                      fmt_millones(rep["MONTO_ESTIMADO"].sum()) + " compra",
                      total=max(len(df), 1))
        self._set_kpi("sobre", round(val_sobre / cap_total * 100), fmt_millones(val_sobre))
        self._set_kpi("dead", round(val_dead / cap_total * 100), fmt_millones(val_dead))
        self._update_barra(vc, len(df))

    def _set_kpi(self, key, valor, detalle, total=100):
        k = self.kpi[key]
        k["meter"].configure(amounttotal=total, amountused=int(valor))
        k["det"].config(text=detalle)

    def _update_barra(self, vc, n):
        n = max(int(n), 1)
        x = 0.0
        for est in BARRA_ORDEN:
            w = int(vc.get(est, 0)) / n
            seg = self._barra_segs[est]
            if w > 0:
                seg.place(relx=x, rely=0, relwidth=w, relheight=1)
                x += w
            else:
                seg.place_forget()

    def _error(self, msg):
        self.btn_generar.config(state="normal")
        self._status("Error: " + msg)
        Messagebox.show_error(msg, "Error al generar")

    # ---- filtros / navegación ----
    def _familias_de(self, df):
        return sorted({cap(x) for x in df["FAMILIA"].dropna().unique() if str(x).lower() != "nan"})

    def _cambio_categoria(self):
        cat = self.cmb_categoria.get()
        if cat and cat != TODAS_CATEGORIAS:
            sub = self.inv[self.inv["RUBRO"].astype(str).str.upper() == cat.upper()]
        else:
            sub = self.inv
        self.cmb_familia["values"] = [TODAS_FAMILIAS] + self._familias_de(sub)
        self.cmb_familia.set(TODAS_FAMILIAS)
        self._aplicar_filtro()

    def _drill(self, estados, label):
        """Clic en un item del rail: filtra por esos estados y resalta el item."""
        self._estados_activos = estados
        for lb, info in self._rail_items.items():
            sel = (lb == label)
            bg = RAIL_SEL if sel else RAIL_BG
            info["acc"].config(bg=info["color"] if sel else RAIL_BG)
            for w in info["widgets"]:
                if w not in (info["acc"],):
                    w.config(bg=bg)
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
            return (df.assign(_k=clave).sort_values("_k", ascending=self._sort_asc, kind="stable")
                      .drop(columns="_k"))
        return df.sort_values(col, ascending=self._sort_asc, kind="stable")

    def _encabezados(self):
        flecha = " ▲" if self._sort_asc else " ▼"
        for key, titulo, _a, _b in self.COLS:
            self.tree.heading(key, text=titulo + (flecha if key == self._sort_col else ""))

    def _aplicar_filtro(self):
        if self.inv is None:
            return
        # scope = categoría/familia/búsqueda (todos los estados) -> contadores del rail.
        scope = filtrar(self.inv, None, self.busqueda.get(),
                        self.cmb_familia.get(), self.cmb_categoria.get())
        # vista = scope + estado seleccionado en el rail.
        df = scope[scope["ESTADO"].isin(self._estados_activos)] if self._estados_activos else scope
        df = self._ordenar_df(df)
        self._encabezados()
        self._vista = df
        self._actualizar_rail(scope)      # el rail se mueve con categoría/familia/búsqueda
        self._actualizar_metricas(df)     # KPIs y barra se mueven con el estado seleccionado

        self.tree.delete(*self.tree.get_children())
        for i, (_, fila) in enumerate(df.iterrows()):
            est = fila["ESTADO"]
            conocido = fila["STOCK_CONOCIDO"]
            stock_txt = fmt_num(fila["STOCK_ACTUAL"]) if conocido else "?"
            cob_txt = fmt_dias(fila["COBERTURA_DIAS"]) if conocido else "—"
            valores = (
                fila["CODIGO"], str(fila["PRODUCTO"])[:60],
                cap(fila["RUBRO"]), cap(fila["FAMILIA"]), fila["ABC"],
                EST_TXT.get(est, est), stock_txt, cob_txt,
                fmt_num(fila["PUNTO_REORDEN"]),
                fmt_num(fila["SUGERIDO_PEDIR"]), fmt_clp(fila["MONTO_ESTIMADO"]),
            )
            tag = EST_TAG.get(est, "impar" if i % 2 else "par")
            self.tree.insert("", "end", values=valores, tags=(tag,))

        monto = df["MONTO_ESTIMADO"].sum()
        self.resumen.config(text=f"{len(df):,} productos · compra {fmt_clp(monto)}".replace(",", "."))

    def _exportar(self):
        if self._vista is None or len(self._vista) == 0:
            Messagebox.show_info("No hay productos en la vista actual.", "Nada que exportar")
            return
        ruta = ex.exportar_excel(self._vista)
        self._status(f"Exportado: {ruta}")
        if Messagebox.yesno(f"Se generó el archivo:\n\n{ruta}\n\n¿Abrirlo ahora?", "Exportado") == "Yes":
            try:
                os.startfile(ruta)
            except Exception:  # noqa: BLE001
                pass


def main():
    root = tb.Window(themename="litera", title="Gestor de Compras 2.0")
    _aplicar_tema(root)
    GestorApp(root)
    root.update_idletasks()
    w, h = 1320, 800
    x = max(0, (root.winfo_screenwidth() - w) // 2)
    y = max(0, (root.winfo_screenheight() - h) // 3)
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.minsize(1120, 700)
    root.lift()
    root.attributes("-topmost", True)
    root.after(900, lambda: root.attributes("-topmost", False))
    root.focus_force()
    root.mainloop()


if __name__ == "__main__":
    main()
