import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")

from loguru import logger
logger.remove()
logger.add(sys.stdout, level="WARNING", format="{level} | {message}", colorize=False)

import pandas as pd

# Leer el archivo directamente
from utils.siigo_parser import parse_siigo_auxiliary
df = parse_siigo_auxiliary("data/transactions/AUXILIAR 2016 - DIC.xlsx")
print("Leido OK:", len(df), "filas")

# Construir lookup simulado
accounts_lookup = {str(c).strip(): {"id": str(c).strip()} for c in df["codigo_cuenta"].unique()}
contacts_map = {n: n for n in df["nit_tercero"].unique() if str(n).strip()}

print("Cuentas en lookup:", len(accounts_lookup))
print("Contactos en map:", len(contacts_map))

# Iterar fila a fila como lo hace transform_to_alegra_format
from utils.validators import validate_date, validate_amount

print("Iterando filas...")
errors = []
for idx, row in df.iterrows():
    try:
        fecha = validate_date(row["fecha"])
        debito = validate_amount(row.get("debito", 0) or 0)
        credito = validate_amount(row.get("credito", 0) or 0)
    except Exception as exc:
        errors.append((idx, str(exc)))

if errors:
    print("Errores en validacion:", errors[:5])
else:
    print("Todas las filas validadas sin errores")

# Construir DataFrame de salida manualmente (como en transform_to_alegra_format)
rows_ok = []
for idx, row in df.iterrows():
    fecha = validate_date(row["fecha"])
    debito = validate_amount(row.get("debito", 0) or 0)
    credito = validate_amount(row.get("credito", 0) or 0)
    nit = str(row.get("nit_tercero", "")).strip()
    contact_id = contacts_map.get(nit, nit)
    code = str(row.get("codigo_cuenta", "")).strip()
    account_data = accounts_lookup.get(code, {})
    account_id = account_data.get("id", code)
    rows_ok.append({
        "date": fecha,
        "description": str(row.get("descripcion", "")).strip(),
        "account": account_id,
        "debit": debito,
        "credit": credito,
        "contact": contact_id,
        "costCenter": str(row.get("centro_costo", "") or "").strip(),
        "observations": "",
        "_numero_comprobante": str(row.get("numero_comprobante", "")).strip(),
    })

result_df = pd.DataFrame(rows_ok)
print("DataFrame construido:", len(result_df), "filas")

# Verificar balance
balance = result_df.groupby("_numero_comprobante")[["debit","credit"]].sum()
balance["diff"] = (balance["debit"] - balance["credit"]).abs()
todas_ok = (balance["diff"] < 0.01).all()
print("Todos los comprobantes balancean:", todas_ok)

print()
print("=== PRIMERAS 5 FILAS DEL RESULTADO ===")
cols = ["date", "description", "account", "debit", "credit", "_numero_comprobante"]
print(result_df[cols].head(5).to_string())
print()
print("MINI TEST COMPLETADO OK")
