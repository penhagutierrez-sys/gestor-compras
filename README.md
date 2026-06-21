# Gestor de Compras 2.0

App de escritorio (Python) para **FERRETERÍA SOLUCENTER LTDA**.

Lee el historial de ventas, lo analiza (medias móviles, clasificación ABC/XYZ,
tendencia 2025→2026) y genera **órdenes de compra sugeridas** que el equipo de
Compras / Abastecimiento / Logística revisa y exporta a Excel.

## Cómo funciona (resumen)

```
Ventas (Excel)  ─┐
                 ├─►  MOTOR  ─►  Órdenes de Compra sugeridas  ─►  Excel
Stock  (Excel)  ─┘     (analiza demanda, ABC/XYZ, tendencia)
```

## Cómo usarlo

1. Instala las librerías (una sola vez):
   ```
   pip install -r requirements.txt
   ```
2. Revisa las rutas de tus archivos en `config.py`.
3. Corre el motor:
   ```
   python main.py
   ```

## Estructura

- `config.py` — rutas de archivos y parámetros del motor.
- `motor/` — el "cerebro": carga de datos y cálculos.
- `main.py` — corre todo el motor de principio a fin.
- `salidas/` — aquí se guardan las órdenes generadas (no se sube a GitHub).

## Importante

Los archivos de datos (`*.xlsx`, `*.csv`) y la carpeta `salidas/` **NO se suben a
GitHub** (ver `.gitignore`), porque contienen información confidencial de la empresa.
