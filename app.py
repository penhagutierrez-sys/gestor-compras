"""
GESTOR DE COMPRAS 2.0 — Ventana de escritorio
=============================================
App simple para el equipo de Compras: genera las órdenes sugeridas con un clic,
las muestra en una tabla (enfocada en los productos MÁS VENDIDOS) y las exporta
a Excel. No hay que tocar código ni terminal.

Para abrirla:  python app.py
"""
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from motor import pipeline
from motor import exportar as ex

# Modos de filtro disponibles (el primero es el que se muestra al abrir).
MODOS = [
    "Reponer ya (stock 0 o por agotarse)",
    "Solo quiebre (stock 0)",
    "Top 50 más vendidos",
    "Clase A",
    "Sin dato de stock",
    "Todos",
]

# Texto e ícono que se muestra en la columna "Estado".
URG_TXT = {
    "QUIEBRE": "⛔ Quiebre",
    "POR AGOTARSE": "⚠ Por agotarse",
    "SIN DATO": "❔ Sin dato",
    "OK": "OK",
}

AZUL = "#1F4E78"
GRIS = "#F2F6FA"


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
        m = (df["PRODUCTO"].astype(str).str.upper().str.contains(texto, regex=False)
             | df["CODIGO"].astype(str).str.upper().str.contains(texto, regex=False))
        df = df[m]
    return df


# --- La ventana -------------------------------------------------------------
class GestorApp:
    COLS = [
        ("CODIGO", "Código", 105, "w"),
        ("PRODUCTO", "Producto", 300, "w"),
        ("ABC", "ABC", 42, "center"),
        ("URGENCIA", "Estado", 120, "center"),
        ("STOCK_ACTUAL", "Stock", 70, "e"),
        ("PRONOSTICO_MENSUAL", "Pronóstico/mes", 95, "e"),
        ("SUGERIDO_PEDIR", "Sugerido pedir", 100, "e"),
        ("MONTO_ESTIMADO", "Monto estimado", 115, "e"),
    ]

    def __init__(self, root):
        self.root = root
        self.ordenes = None
        root.title("Gestor de Compras 2.0")
        root.geometry("1040x640")
        root.minsize(900, 520)

        self._estilo()
        self._cabecera()
        self._controles()
        self._tabla()
        self._barra_estado()

        # Apenas abre, genera las órdenes en segundo plano.
        self._generar()

    # ---- construcción de la interfaz ----
    def _estilo(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("Treeview", rowheight=24, font=("Segoe UI", 9))
        s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _cabecera(self):
        head = tk.Frame(self.root, bg=AZUL)
        head.pack(fill="x")
        tk.Label(head, text="🛒  Gestor de Compras 2.0", bg=AZUL, fg="white",
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=16, pady=10)
        tk.Label(head, text="Productos a reponer — stock 0 o por agotarse",
                 bg=AZUL, fg="#CFE0F1", font=("Segoe UI", 9)).pack(side="left", pady=10)

    def _controles(self):
        barra = ttk.Frame(self.root, padding=(12, 10))
        barra.pack(fill="x")

        ttk.Label(barra, text="Ver:").pack(side="left")
        self.cmb = ttk.Combobox(barra, values=MODOS, state="readonly", width=20)
        self.cmb.current(0)
        self.cmb.pack(side="left", padx=(4, 14))
        self.cmb.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtro())

        ttk.Label(barra, text="Buscar:").pack(side="left")
        self.busqueda = ttk.Entry(barra, width=26)
        self.busqueda.pack(side="left", padx=(4, 14))
        self.busqueda.bind("<KeyRelease>", lambda e: self._aplicar_filtro())

        self.btn_generar = ttk.Button(barra, text="🔄  Generar / Actualizar",
                                      command=self._generar)
        self.btn_generar.pack(side="left")
        self.btn_export = ttk.Button(barra, text="⬇  Exportar a Excel",
                                     command=self._exportar, state="disabled")
        self.btn_export.pack(side="left", padx=8)

        self.resumen = ttk.Label(self.root, text="", font=("Segoe UI", 9, "bold"),
                                 padding=(14, 0))
        self.resumen.pack(fill="x")

    def _tabla(self):
        cont = ttk.Frame(self.root, padding=(12, 6))
        cont.pack(fill="both", expand=True)

        cols = [c[0] for c in self.COLS]
        self.tree = ttk.Treeview(cont, columns=cols, show="headings")
        for key, titulo, ancho, anchor in self.COLS:
            self.tree.heading(key, text=titulo)
            self.tree.column(key, width=ancho, anchor=anchor, stretch=(key == "PRODUCTO"))
        # Colores por urgencia (para que salte a la vista qué reponer).
        self.tree.tag_configure("impar", background=GRIS)
        self.tree.tag_configure("quiebre", background="#F8D2D2")    # rojo suave
        self.tree.tag_configure("agotarse", background="#FCEFC7")   # amarillo suave
        self.tree.tag_configure("sindato", background="#E9ECEF")    # gris

        sb = ttk.Scrollbar(cont, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _barra_estado(self):
        self.estado = tk.Label(self.root, text="", anchor="w", bg="#E8E8E8",
                               font=("Segoe UI", 8))
        self.estado.pack(fill="x", side="bottom")

    # ---- lógica ----
    def _status(self, msg):
        self.estado.config(text="  " + msg)

    def _generar(self):
        self.btn_generar.config(state="disabled")
        self.btn_export.config(state="disabled")
        self._status("Procesando... (cargando ventas y stock, ~5 segundos)")
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
        self._aplicar_filtro()
        self._status(f"Listo — {len(ordenes):,} productos a pedir en total.")

    def _error(self, msg):
        self.btn_generar.config(state="normal")
        self._status("Error: " + msg)
        messagebox.showerror("Error al generar", msg)

    def _aplicar_filtro(self):
        if self.ordenes is None:
            return
        df = filtrar(self.ordenes, self.cmb.get(), self.busqueda.get())
        self._vista = df  # lo que se ve = lo que se exporta

        self.tree.delete(*self.tree.get_children())
        tag_urg = {"QUIEBRE": "quiebre", "POR AGOTARSE": "agotarse", "SIN DATO": "sindato"}
        for i, (_, fila) in enumerate(df.iterrows()):
            urg = fila["URGENCIA"]
            # Si no conocemos el stock, mostramos "?" en vez de un 0 engañoso.
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
            tag = tag_urg.get(urg, "impar" if i % 2 else "par")
            self.tree.insert("", "end", values=valores, tags=(tag,))

        monto = df["MONTO_ESTIMADO"].sum()
        self.resumen.config(
            text=f"Mostrando {len(df):,} productos  ·  Monto estimado: {fmt_clp(monto)}")

    def _exportar(self):
        if getattr(self, "_vista", None) is None or len(self._vista) == 0:
            messagebox.showinfo("Nada que exportar", "No hay productos en la vista actual.")
            return
        ruta = ex.exportar_excel(self._vista)
        self._status(f"Exportado: {ruta}")
        if messagebox.askyesno("Exportado",
                               f"Se generó el archivo:\n\n{ruta}\n\n¿Abrirlo ahora?"):
            try:
                os.startfile(ruta)  # abre el Excel (Windows)
            except Exception:  # noqa: BLE001
                pass


def main():
    root = tk.Tk()
    GestorApp(root)

    # Centrar la ventana y traerla al frente (a veces abre detrás de otras).
    root.update_idletasks()
    w, h = 1040, 640
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
