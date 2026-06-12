"""
Genera el archivo Excel para importar en Alegra desde el Libro Auxiliar de Siigo.
Formato: columnas exactas de la Plantilla de Importacion de Comprobantes Contables.

Uso:
  python _generar_importacion.py                          # usa AUXILIAR 2016 - DIC.xlsx
  python _generar_importacion.py "AUXILIAR 2017.xlsx"    # archivo especifico
  python _generar_importacion.py "AUXILIAR 2017 - ENE.xlsx"

Salida: data/output/ALEGRA_IMPORT_<nombre_archivo>.xlsx
"""
import sys, io
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
logger.remove()
logger.add(sys.stdout, level="INFO", format="{level:<8} | {message}", colorize=False)

from pathlib import Path
from datetime import datetime
import pandas as pd

from utils.siigo_parser import parse_siigo_auxiliary

# ─── Rutas ────────────────────────────────────────────────────────────────────
if len(sys.argv) > 1:
    _input_name = sys.argv[1]
else:
    _input_name = "AUXILIAR 2016 - DIC.xlsx"

SIIGO_FILE  = f"data/transactions/{_input_name}"
OUTPUT_DIR  = Path("data/output")
_stem       = Path(_input_name).stem.replace(" ", "_").replace("-", "")
OUTPUT_FILE = OUTPUT_DIR / f"ALEGRA_IMPORT_{_stem}.xlsx"

# ─── Configuracion ─────────────────────────────────────────────────────────────
TIPO_DEFAULT       = "Ajuste contable"
NUMERACION_DEFAULT = "Ajuste contable"

# Mapeo de código Siigo -> nombre EXACTO en catálogo Alegra
# (cuentas con nombre específico en Siigo que coincide o se acerca a Alegra)
# Para códigos no listados, se usa el nombre Siigo en Title Case (Alegra los crea)
ACCOUNT_CODE_MAP = {
    # Activos — existen en Alegra
    "1105050100": "Caja general",
    "1330050000": "A proveedores",
    "1330100000": "A contratistas",
    "1355200100": "Impuestos descontables",
    # Activos específicos Azahar — se crearán en Alegra
    "1110050100": "Davivienda Cta Cte 6544",
    "1520100100": "Molino Mythos One",
    "1520100200": "Contenedor Tienda 93",
    "1528050100": "Computador Oneposi",
    "1528050200": "Impresora",
    "1528050300": "Bafle",
    "1528050400": "Tablet",
    "1536950100": "Molino Mythos",
    "1536950200": "Molino Mahlkonig K30",
    "1536950300": "Meson De Preparacion En Marmol",
    "1536950400": "Activos Varios Aportes",
    "1536950500": "Actvo Menaje",
    # Pasivos — existen en Alegra
    "2205050000": "Proveedores nacionales",
    "2335250000": "Honorarios",
    "2335300000": "Servicios técnicos",
    "2365150200": "Retenciones honorarios y comisiones 11% por pagar",
    "2365250400": "Retenciones servicios 4% por pagar",
    "2365250700": "Retenciones arriendo 3.5% por pagar",
    "2365400200": "Retenciones compra 2.5% por pagar",
    "2365950000": "Retenciones por pagar",
    "2408100100": "IVA descontable por compras",
    "2408150300": "Descontable por servicios",
    # Pasivos específicos Azahar — se crearán
    "2335950200": "Servicios por pagar",
    "2355100000": "Socios",
    "2365150300": "Honorarios declarantes 6%",
    # Patrimonio — existen en Alegra
    "3105050000": "Capital autorizado",
    "3105100000": "Capital por suscribir (DB)",
    "3105150000": "Capital suscrito por cobrar (DB)",
    "3205050000": "Prima en colocación de acciones",
    "3610050000": "Pérdida del ejercicio",
    # Ingresos — existen
    "4295810000": "Ajuste al peso",
    # Gastos — existen en Alegra
    "5110350000": "Asesoría técnica",
    "5120100000": "Construcciones y edificaciones",
    "5135150000": "Asistencia técnica",
    "5140150000": "Trámites y licencias",
    "5145250000": "Equipo de computación y comunicación",
    "5195950100": "Ajustes por aproximaciones en cálculos",
    "5305050000": "Gastos bancarios",
    "5305950100": "Gastos bancarios",
}

# Nombres de columnas EXACTOS de la plantilla Alegra (Hoja "Plantilla")
COLUMNS = [
    "Número",
    "Fecha \n (Requerido)",
    "Tipo de comprobante contable           (Requerido)",
    "Numeración contable (Requerido)",
    "Observaciones         (Opcional)",
    "Empleado \n(Requerido Nómina)",
    "Cuenta contable (Requerido)",
    "Número identificación del contacto (Opcional)",
    "Nombre del Contacto (Opcional)",
    "Descripción               (Opcional)",
    "Centro de costo     (Opcional)",
    "Débito      (Requerido)",
    "Crédito      (Requerido)",
]

print("=" * 60)
print("GENERANDO ARCHIVO DE IMPORTACION PARA ALEGRA")
print(f"Fuente : {SIIGO_FILE}")
print(f"Salida : {OUTPUT_FILE}")
print("=" * 60)
print()

# ─── 1. Parsear Siigo ─────────────────────────────────────────────────────────
logger.info(f"Leyendo {SIIGO_FILE}...")
df = parse_siigo_auxiliary(SIIGO_FILE)
print(f"Transacciones leidas: {len(df)} filas, {df['numero_comprobante'].nunique()} comprobantes")

MESES_ES = {
    1: "ENE", 2: "FEB", 3: "MAR", 4: "ABR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AGO", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DIC",
}

def _build_row(fila, comp_num, fecha_str, numero_comp):
    debito  = float(fila["debito"]  or 0)
    credito = float(fila["credito"] or 0)
    nit = str(fila.get("nit_tercero", "") or "").strip()
    nombre_contacto = str(fila.get("nombre_tercero", "") or "").strip()
    if nit in ("0", ""):
        nit = ""
        nombre_contacto = ""
    codigo = str(fila.get("codigo_cuenta", "") or "").strip()
    nombre_raw = str(fila.get("nombre_cuenta", "") or "").strip()
    if codigo in ACCOUNT_CODE_MAP:
        cuenta = ACCOUNT_CODE_MAP[codigo]
    elif codigo.startswith("1592"):
        cuenta = "Depreciacion Acumulada"
    else:
        cuenta = nombre_raw.title()
    return {
        "Número":                                              comp_num,
        "Fecha \n (Requerido)":                                fecha_str,
        "Tipo de comprobante contable           (Requerido)":  TIPO_DEFAULT,
        "Numeración contable (Requerido)":                     NUMERACION_DEFAULT,
        "Observaciones         (Opcional)":                    str(numero_comp),
        "Empleado \n(Requerido Nómina)":                       "",
        "Cuenta contable (Requerido)":                         cuenta,
        "Número identificación del contacto (Opcional)":       nit,
        "Nombre del Contacto (Opcional)":                      nombre_contacto,
        "Descripción               (Opcional)":                str(fila.get("descripcion", "") or "").strip(),
        "Centro de costo     (Opcional)":                      str(fila.get("centro_costo", "") or "").strip(),
        "Débito      (Requerido)":                             debito if debito else "",
        "Crédito      (Requerido)":                            credito if credito else "",
    }

def _save_chunk(rows, tag, output_dir, stem):
    chunk_df = pd.DataFrame(rows, columns=COLUMNS)
    # renumerar comprobantes localmente (1, 2, 3...)
    old_nums = chunk_df["Número"].unique()
    num_map = {v: i+1 for i, v in enumerate(old_nums)}
    chunk_df = chunk_df.assign(**{"Número": chunk_df["Número"].map(num_map)})
    out = output_dir / f"ALEGRA_IMPORT_{stem}_{tag}.xlsx"
    chunk_df.to_excel(out, sheet_name="Plantilla", index=False, engine="openpyxl")
    size_kb = out.stat().st_size / 1024
    ncomp = chunk_df["Número"].nunique()
    print(f"  [{tag}]  {len(rows):>5} filas  {ncomp:>4} comprobantes  {size_kb:>6.1f} KB  ->  {out.name}")
    return out, size_kb

# ─── 2. Construir filas ────────────────────────────────────────────────────────
comp_num = 0
all_rows = []

for numero_comp, grupo in df.groupby("numero_comprobante", sort=False):
    comp_num += 1
    fecha_raw = str(grupo.iloc[0]["fecha"]).strip()
    try:
        fecha_str = datetime.strptime(fecha_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        fecha_str = fecha_raw

    for _, fila in grupo.iterrows():
        all_rows.append(_build_row(fila, comp_num, fecha_str, numero_comp))

result_df = pd.DataFrame(all_rows, columns=COLUMNS)
print(f"Filas generadas: {len(result_df)} ({comp_num} comprobantes)")

# ─── 3. Exportar (dividir por mes si supera el limite) ────────────────────────
MAX_KB  = 400
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Prueba tamaño del archivo completo
result_df.to_excel(OUTPUT_FILE, sheet_name="Plantilla", index=False, engine="openpyxl")
size_kb = OUTPUT_FILE.stat().st_size / 1024

print()
if size_kb <= MAX_KB:
    print("=" * 60)
    print("ARCHIVO GENERADO EXITOSAMENTE")
    print("=" * 60)
    print(f"  Ruta        : {OUTPUT_FILE.resolve()}")
    print(f"  Filas       : {len(all_rows)}")
    print(f"  Comprobantes: {comp_num}")
    print(f"  Tamanio     : {size_kb:.1f} KB (limite Alegra: 450 KB)")
    print()
    print("Paso siguiente:")
    print("  1. Abre Alegra -> Contabilidad -> Comprobante contable")
    print("  2. Mas acciones -> Importar comprobantes")
    print(f"  3. Sube el archivo: {OUTPUT_FILE.name}")
else:
    # Eliminar el archivo unico que supera el limite
    OUTPUT_FILE.unlink(missing_ok=True)

    print("=" * 60)
    print(f"ARCHIVO GRANDE ({size_kb:.0f} KB > {MAX_KB} KB) — dividiendo por mes")
    print("=" * 60)

    # Agrupar filas por mes usando la columna de fecha (DD/MM/YYYY)
    month_rows: dict = {}
    for row in all_rows:
        fecha = row["Fecha \n (Requerido)"]
        try:
            dt = datetime.strptime(fecha, "%d/%m/%Y")
            key = (dt.year, dt.month)
        except ValueError:
            key = (0, 0)
        month_rows.setdefault(key, []).append(row)

    generated = []
    for (yr, mo) in sorted(month_rows.keys()):
        tag = MESES_ES.get(mo, str(mo)) if yr else "SINMES"
        out, kb = _save_chunk(month_rows[(yr, mo)], tag, OUTPUT_DIR, _stem)
        generated.append((out, kb))

    print()
    print(f"Archivos generados: {len(generated)}")
    print()
    print("Subir a Alegra EN ESTE ORDEN:")
    for i, (out, kb) in enumerate(generated, 1):
        print(f"  {i:>2}. {out.name}  ({kb:.0f} KB)")
