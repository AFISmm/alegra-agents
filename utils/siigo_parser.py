"""
Parser para archivos de Libro Auxiliar exportados desde Siigo.

El formato tiene:
- Filas 0-5: encabezado decorativo de Siigo
- Fila 6: nombres de columnas
- Filas siguientes: mezcla de cabeceras de cuenta, filas de datos, y totales

Este módulo extrae solo las filas de transacciones reales y las convierte
al formato estándar que espera TemplateAgent.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from loguru import logger


# Mapeo de índice de columna Siigo → nombre estándar nuestro
SIIGO_COL_MAP = {
    1:  "codigo_cuenta",      # CUENTA
    2:  "nombre_cuenta",      # DESCRIPCION
    4:  "nit_tercero",        # NIT
    7:  "nombre_tercero",     # NOMBRE
    8:  "_comprobante_raw",   # COMPROBANTE (sin parsear)
    9:  "fecha",              # FECHA
    10: "descripcion",        # DETALLE
    12: "centro_costo",       # CENTRO COSTO
    15: "debito",             # DEBITOS
    16: "credito",            # CREDITOS
}

# Centro costo por defecto de Siigo (equivale a "sin centro de costo")
_CENTRO_COSTO_VACIO = {"0000-000", "0000 000", "0000", ""}


def _comprobante_base(raw: str) -> str:
    """Extrae el número base del comprobante (sin el número de línea final).

    Ejemplo: 'N 001 00000000005 00005' → 'N 001 00000000005'
    """
    m = re.match(r"([A-Z]\s+\d+\s+\d+)", str(raw).strip())
    return m.group(1).strip() if m else str(raw).strip()


def _to_float(val) -> float:
    try:
        return round(float(str(val).strip().replace(",", "").replace(" ", "")), 2)
    except (ValueError, TypeError):
        return 0.0


def _infer_tipo_tercero(codigo_cuenta: str) -> str:
    """Heurística básica sobre el PUC colombiano para inferir tipo de tercero."""
    code = str(codigo_cuenta).strip()
    if code.startswith("22"):   # Proveedores nacionales/extranjeros
        return "provider"
    if code.startswith("13") or code.startswith("14"):  # Cuentas por cobrar comerciales
        return "client"
    return "other"


def is_siigo_auxiliary(filepath: str | Path) -> bool:
    """Detecta si un archivo xlsx/xls es un auxiliar exportado de Siigo."""
    try:
        sample = pd.read_excel(filepath, dtype=str, header=None, nrows=3)
        first_cell = str(sample.iloc[0, 0]).strip()
        return "siigo" in first_cell.lower() or "libro auxiliar" in first_cell.lower()
    except Exception:
        return False


def parse_siigo_auxiliary(filepath: str | Path) -> pd.DataFrame:
    """
    Lee un Libro Auxiliar de Siigo y retorna un DataFrame en el formato
    estándar de transacciones del proyecto.

    Columnas de salida:
      fecha, descripcion, nit_tercero, nombre_tercero, tipo_tercero,
      codigo_cuenta, nombre_cuenta, debito, credito,
      numero_comprobante, centro_costo
    """
    logger.info(f"SiigoParser: leyendo '{Path(filepath).name}'...")
    raw = pd.read_excel(filepath, dtype=str, header=None)
    logger.debug(f"SiigoParser: {len(raw)} filas brutas leídas.")

    # ── 1. Filtrar solo filas de transacciones ────────────────────────────
    # Aceptar YYYY-MM-DD (ISO) y YYYY/MM/DD (formato Siigo cierre periodo 13)
    col_fecha = raw.iloc[:, 9]
    mask_data = col_fecha.str.contains(r"\d{4}[-/]\d{2}[-/]\d{2}", na=False)
    datos = raw[mask_data].copy().reset_index(drop=True)
    logger.info(f"SiigoParser: {len(datos)} filas de transacciones identificadas.")

    if datos.empty:
        raise ValueError("No se encontraron filas de transacciones en el archivo Siigo.")

    # ── 2. Extraer columnas por índice ────────────────────────────────────
    out: dict[str, list] = {col: [] for col in SIIGO_COL_MAP.values()}
    out["tipo_tercero"] = []
    out["numero_comprobante"] = []

    for _, row in datos.iterrows():
        for idx, col_name in SIIGO_COL_MAP.items():
            val = str(row.iloc[idx]).strip() if idx < len(row) else ""
            out[col_name].append(val)
        out["tipo_tercero"].append(_infer_tipo_tercero(str(row.iloc[1]).strip()))
        out["numero_comprobante"].append(_comprobante_base(str(row.iloc[8]).strip()))

    df = pd.DataFrame(out).copy()

    # ── 3. Normalizar NIT ─────────────────────────────────────────────────
    df = df.assign(nit_tercero=df["nit_tercero"].str.replace("^0$", "", regex=True))
    mask_sin_nit = df["nit_tercero"].str.strip() == ""
    df.loc[mask_sin_nit, "nombre_tercero"] = df.loc[mask_sin_nit, "descripcion"].to_numpy()

    # ── 4. Normalizar fecha - siempre YYYY-MM-DD ──────────────────────────
    # Periodo contable 13 (cierre de año en Siigo) se mapea al 31/12
    def _normalize_date(val: str) -> str:
        val = val.strip()
        m = re.match(r"(\d{4})[-/](\d{2})[-/](\d{2})", val)
        if not m:
            return val[:10]
        year, month, day = m.group(1), m.group(2), m.group(3)
        if int(month) > 12:
            month = "12"
        if int(day) > 31:
            day = "31"
        return f"{year}-{month}-{day}"

    df = df.assign(
        fecha=df["fecha"].apply(_normalize_date),
        debito=df["debito"].apply(_to_float),
        credito=df["credito"].apply(_to_float),
        centro_costo=df["centro_costo"].apply(
            lambda x: "" if x.strip() in _CENTRO_COSTO_VACIO else x.strip()
        ),
    )

    # ── 7. Eliminar columna auxiliar ──────────────────────────────────────
    if "_comprobante_raw" in df.columns:
        df.drop(columns=["_comprobante_raw"], inplace=True)

    # ── 8. Reordenar columnas al estándar del proyecto ────────────────────
    columnas_orden = [
        "fecha", "descripcion", "nit_tercero", "nombre_tercero", "tipo_tercero",
        "codigo_cuenta", "nombre_cuenta", "debito", "credito",
        "numero_comprobante", "centro_costo",
    ]
    df = df[[c for c in columnas_orden if c in df.columns]]

    logger.success(
        f"SiigoParser: {len(df)} transacciones parseadas, "
        f"{df['numero_comprobante'].nunique()} comprobantes únicos."
    )
    return df
