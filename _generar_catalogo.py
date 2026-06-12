"""
Genera el archivo Excel para importar el Catálogo de Cuentas completo en Alegra.
Recopila TODOS los códigos de cuenta de todos los AUXILIAR files.

Uso: python _generar_catalogo.py
Salida: data/output/ALEGRA_CATALOGO_CUENTAS.xlsx
"""
import sys, io
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
from utils.siigo_parser import parse_siigo_auxiliary
import pandas as pd

OUTPUT_FILE = Path("data/output/ALEGRA_CATALOGO_CUENTAS.xlsx")

# Naturaleza por clase PUC (primer dígito)
NATURALEZA = {
    "1": "Débito",   # Activos
    "2": "Crédito",  # Pasivos
    "3": "Crédito",  # Patrimonio
    "4": "Crédito",  # Ingresos
    "5": "Débito",   # Gastos
    "6": "Débito",   # Costos de ventas
    "7": "Débito",   # Costos de producción
    "8": "Débito",   # Cuentas de orden deudoras
    "9": "Crédito",  # Cuentas de orden acreedoras
}

# Nombres estándar PUC Colombia para cuentas padre (2-4 dígitos)
# Se usan cuando no hay un nombre mejor en el Siigo
PUC_NOMBRES = {
    # CLASE
    "1": "ACTIVO",
    "2": "PASIVO",
    "3": "PATRIMONIO",
    "4": "INGRESOS",
    "5": "GASTOS",
    "6": "COSTO DE VENTAS",
    "7": "COSTOS DE PRODUCCION O DE OPERACION",
    # GRUPOS
    "11": "DISPONIBLE",
    "12": "INVERSIONES",
    "13": "DEUDORES",
    "14": "INVENTARIOS",
    "15": "PROPIEDADES PLANTA Y EQUIPO",
    "16": "INTANGIBLES",
    "17": "DIFERIDOS",
    "18": "OTROS ACTIVOS",
    "19": "VALORIZACIONES",
    "21": "OBLIGACIONES FINANCIERAS",
    "22": "PROVEEDORES",
    "23": "CUENTAS POR PAGAR",
    "24": "IMPUESTOS GRAVAMENES Y TASAS",
    "25": "OBLIGACIONES LABORALES",
    "26": "PASIVOS ESTIMADOS Y PROVISIONES",
    "27": "DIFERIDOS",
    "28": "OTROS PASIVOS",
    "29": "BONOS Y PAPELES COMERCIALES",
    "31": "CAPITAL SOCIAL",
    "32": "SUPERAVIT DE CAPITAL",
    "33": "RESERVAS",
    "34": "REVALORIZACION DEL PATRIMONIO",
    "36": "RESULTADOS DEL EJERCICIO",
    "37": "RESULTADOS DE EJERCICIOS ANTERIORES",
    "38": "SUPERAVIT POR VALORIZACIONES",
    "41": "INGRESOS OPERACIONALES",
    "42": "INGRESOS NO OPERACIONALES",
    "43": "DEVOLUCIONES REBAJAS Y DESCUENTOS EN VENTAS",
    "51": "GASTOS OPERACIONALES DE ADMINISTRACION",
    "52": "GASTOS OPERACIONALES DE VENTAS",
    "53": "GASTOS NO OPERACIONALES",
    "54": "IMPUESTO DE RENTA Y COMPLEMENTARIOS",
    "59": "GANANCIAS Y PERDIDAS",
    "61": "COSTO DE VENTAS Y DE PRESTACION DE SERVICIOS",
    "63": "DEVOLUCIONES REBAJAS Y DESCUENTOS EN COMPRAS",
    # CUENTAS (4 dígitos) - las más comunes
    "1105": "CAJA",
    "1110": "BANCOS",
    "1305": "CLIENTES",
    "1320": "CUENTAS CORRIENTES COMERCIALES",
    "1325": "CUENTAS POR COBRAR A SOCIOS",
    "1330": "ANTICIPOS Y AVANCES",
    "1335": "DEPOSITOS",
    "1340": "PROMESAS DE COMPRAVENTA",
    "1345": "INGRESOS POR COBRAR",
    "1355": "ANTICIPO DE IMPUESTOS Y CONTRIBUCIONES",
    "1380": "DEUDORES VARIOS",
    "1405": "MATERIAS PRIMAS",
    "1430": "PRODUCTOS EN PROCESO",
    "1435": "MERCANCIAS NO FABRICADAS POR LA EMPRESA",
    "1455": "MATERIALES REPUESTOS Y ACCESORIOS",
    "1516": "CONSTRUCCIONES Y EDIFICACIONES",
    "1520": "MAQUINARIA Y EQUIPO",
    "1524": "EQUIPO DE OFICINA",
    "1528": "EQUIPO DE COMPUTACION Y COMUNICACION",
    "1536": "MUEBLES Y ENSERES",
    "1592": "DEPRECIACION ACUMULADA",
    "1635": "LICENCIAS",
    "1705": "GASTOS PAGADOS POR ANTICIPADO",
    "1710": "CARGOS DIFERIDOS",
    "2205": "PROVEEDORES NACIONALES",
    "2335": "COSTOS Y GASTOS POR PAGAR",
    "2355": "DEUDAS CON ACCIONISTAS",
    "2365": "RETENCIONES EN LA FUENTE",
    "2368": "IMPUESTO A LAS VENTAS RETENIDO",
    "2370": "RETENCIONES Y APORTES DE NOMINA",
    "2380": "ACREEDORES VARIOS",
    "2404": "IMPUESTO SOBRE LAS VENTAS",
    "2408": "IMPUESTO A LAS VENTAS POR PAGAR",
    "2412": "IMPUESTO DE INDUSTRIA Y COMERCIO",
    "2495": "OTROS IMPUESTOS",
    "2505": "SALARIOS POR PAGAR",
    "2510": "CESANTIAS CONSOLIDADAS",
    "2515": "INTERESES SOBRE CESANTIAS",
    "2525": "VACACIONES CONSOLIDADAS",
    "2610": "PARA OBLIGACIONES LABORALES",
    "2815": "INGRESOS RECIBIDOS POR ANTICIPADO",
    "3105": "CAPITAL SUSCRITO Y PAGADO",
    "3205": "PRIMA EN COLOCACION DE ACCIONES",
    "3610": "PERDIDA DEL EJERCICIO",
    "3710": "PERDIDAS ACUMULADAS",
    "4120": "COMERCIO AL POR MAYOR Y AL POR MENOR",
    "4135": "INDUSTRIAS MANUFACTURERAS",
    "4140": "ACTIVIDADES DE HOTELES RESTAURANTES",
    "4250": "FINANCIEROS",
    "4255": "RECUPERACIONES",
    "4295": "DIVERSOS",
    "5105": "GASTOS DE PERSONAL",
    "5110": "HONORARIOS",
    "5115": "IMPUESTOS",
    "5120": "ARRENDAMIENTOS",
    "5135": "SERVICIOS",
    "5140": "GASTOS LEGALES",
    "5145": "MANTENIMIENTO Y REPARACIONES",
    "5155": "GASTOS DE VIAJE",
    "5195": "DIVERSOS",
    "5205": "GASTOS DE PERSONAL",
    "5210": "HONORARIOS",
    "5215": "IMPUESTOS",
    "5220": "ARRENDAMIENTOS",
    "5225": "CONTRIBUCIONES Y AFILIACIONES",
    "5230": "SEGUROS",
    "5235": "SERVICIOS",
    "5240": "GASTOS LEGALES",
    "5245": "MANTENIMIENTO Y REPARACIONES",
    "5250": "ADECUACIONES E INSTALACIONES",
    "5255": "GASTOS DE VIAJE",
    "5260": "DEPRECIACIONES",
    "5265": "AMORTIZACIONES",
    "5295": "DIVERSOS",
    "5305": "GASTOS FINANCIEROS",
    "5315": "PERDIDAS EN RETIRO DE BIENES",
    "5395": "GASTOS EXTRAORDINARIOS",
    "5405": "IMPUESTO DE RENTA Y COMPLEMENTARIOS",
    "6120": "COMERCIO AL POR MAYOR Y AL POR MENOR",
    "6135": "INDUSTRIAS MANUFACTURERAS",
}


def get_naturaleza(code: str) -> str:
    return NATURALEZA.get(code[0], "Débito")


def get_parent_name(parent_code: str, child_names: dict) -> str:
    if parent_code in PUC_NOMBRES:
        return PUC_NOMBRES[parent_code].title()
    # Busca en los nombres hijos si hay un prefijo compartido
    candidates = [n for c, n in child_names.items() if c.startswith(parent_code) and c != parent_code]
    if candidates:
        # Usa el nombre del hijo más corto como referencia
        return f"Grupo {parent_code}"
    return f"Grupo {parent_code}"


print("=" * 60)
print("GENERANDO CATALOGO DE CUENTAS PARA ALEGRA")
print("=" * 60)

# ─── 1. Recopilar todas las cuentas de todos los AUXILIAR files ───────────────
files = sorted(Path("data/transactions").glob("AUXILIAR*.xlsx"))
leaf_accounts: dict = {}  # code -> name (Siigo original)

for f in files:
    print(f"  Leyendo {f.name}...")
    try:
        df = parse_siigo_auxiliary(str(f))
        for _, row in df[["codigo_cuenta", "nombre_cuenta"]].drop_duplicates().iterrows():
            code = str(row["codigo_cuenta"]).strip()
            name = str(row["nombre_cuenta"]).strip()
            if code and len(code) >= 4:
                if code not in leaf_accounts:
                    leaf_accounts[code] = name
    except Exception as e:
        print(f"    ERROR: {e}")

print(f"\nCuentas hoja recopiladas: {len(leaf_accounts)}")

# Prefijos que se consolidan en la cuenta padre de 4 dígitos.
# Alegra permite máximo 35 cuentas de Activo con naturaleza Crédito.
# 1592 = Depreciación acumulada: contra-activo con naturaleza Crédito → consolidar.
CONSOLIDAR_EN_PADRE = {
    "1592",  # Depreciacion Acumulada — todas las sub-cuentas van al padre
}

# ─── 2. Generar jerarquía completa (cuentas padre intermedias) ─────────────────
all_codes: dict = {}  # code -> (name, tipo)

for code, name in leaf_accounts.items():
    # Si el código cae dentro de un grupo consolidado, sólo agregar la cuenta padre de 4 dígitos
    consolidado = next((p for p in CONSOLIDAR_EN_PADRE if code.startswith(p) and len(code) > len(p)), None)
    if consolidado:
        if consolidado not in all_codes:
            padre_name = PUC_NOMBRES.get(consolidado, f"Grupo {consolidado}").title()
            all_codes[consolidado] = (padre_name, "Cuenta de movimiento")
        continue  # No agregar la sub-cuenta individual

    # Añadir la cuenta hoja
    all_codes[code] = (name.title(), "Cuenta de movimiento")

    # Generar padres: 8, 6, 4 dígitos
    for length in [8, 6, 4]:
        if len(code) > length:
            parent = code[:length]
            if parent not in all_codes:
                parent_name = PUC_NOMBRES.get(parent, f"Grupo {parent}").title()
                all_codes[parent] = (parent_name, "Cuenta mayor")

# Añadir grupos de 2 dígitos
for code in list(all_codes.keys()):
    if len(code) >= 4:
        grupo = code[:2]
        if grupo not in all_codes:
            all_codes[grupo] = (PUC_NOMBRES.get(grupo, f"Grupo {grupo}").title(), "Cuenta mayor")

print(f"Cuentas totales con jerarquía: {len(all_codes)}")

# ─── 3. Construir DataFrame ────────────────────────────────────────────────────
rows = []
for code in sorted(all_codes.keys()):
    name, tipo = all_codes[code]
    rows.append({
        "Código": code,
        "Nombre": name,
        "Tipo": tipo,
        "Naturaleza": get_naturaleza(code),
    })

df_out = pd.DataFrame(rows)
print(f"Filas en el catálogo: {len(df_out)}")

# ─── 4. Exportar ──────────────────────────────────────────────────────────────
Path("data/output").mkdir(parents=True, exist_ok=True)
df_out.to_excel(OUTPUT_FILE, sheet_name="Catalogo", index=False, engine="openpyxl")

size_kb = OUTPUT_FILE.stat().st_size / 1024
print()
print("=" * 60)
print("ARCHIVO GENERADO")
print("=" * 60)
print(f"  Ruta   : {OUTPUT_FILE.resolve()}")
print(f"  Filas  : {len(df_out)}")
print(f"  Tamaño : {size_kb:.1f} KB")
print()
print("Vista previa (10 primeras filas):")
print(df_out.head(10).to_string(index=False))
print()
print("Paso siguiente:")
print("  Alegra -> Contabilidad -> Sincronizacion contable")
print("  -> Migrar informacion contable -> Catalogo de cuentas")
print(f"  -> Subir: {OUTPUT_FILE.name}")
