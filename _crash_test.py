"""Aislamiento del crash — prueba cada operacion por separado."""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from loguru import logger
logger.remove()
logger.add(sys.stdout, level="WARNING", format="{level} | {message}", colorize=False)

import pandas as pd

print("1. pd.to_datetime test...")
ts = pd.to_datetime("2016-12-01")
print("   OK:", ts.strftime("%Y-%m-%d"))

print("2. Lectura del archivo...")
from utils.siigo_parser import parse_siigo_auxiliary
df = parse_siigo_auxiliary("data/transactions/AUXILIAR 2016 - DIC.xlsx")
print("   OK:", len(df), "filas")

print("3. Primera fila del DataFrame...")
row = df.iloc[0]
print("   fecha:", repr(row["fecha"]))
print("   debito:", repr(row["debito"]))
print("   credito:", repr(row["credito"]))

print("4. validate_date sobre primera fecha...")
from utils.validators import validate_date, validate_amount
fecha = validate_date(row["fecha"])
print("   OK:", fecha)

print("5. validate_amount sobre primer debito...")
d = validate_amount(row["debito"])
print("   OK:", d)

print("6. Iteracion manual sobre primeras 3 filas...")
for i, (idx, r) in enumerate(df.head(3).iterrows()):
    vd = validate_date(r["fecha"])
    vdeb = validate_amount(r["debito"])
    vcred = validate_amount(r["credito"])
    print(f"   fila {i}: fecha={vd} deb={vdeb} cred={vcred} cuenta={r['codigo_cuenta']}")

print("7. transform_to_alegra_format con 3 filas de prueba...")
from agents.template_agent import TemplateAgent
agent = TemplateAgent()
df3 = df.head(6).copy()
accounts_lookup = {str(c).strip(): {"id": str(c).strip()} for c in df3["codigo_cuenta"].unique()}
contacts_map = {}
result = agent.transform_to_alegra_format(df3, contacts_map, accounts_lookup)
print("   OK:", len(result), "filas transformadas")

print("8. transform completo (122 filas)...")
contacts_map_full = {}
nits = df[df["nit_tercero"].str.strip() != ""]["nit_tercero"].unique()
for n in nits:
    contacts_map_full[n] = n
accounts_lookup_full = {str(c).strip(): {"id": str(c).strip()} for c in df["codigo_cuenta"].unique()}
result_full = agent.transform_to_alegra_format(df, contacts_map_full, accounts_lookup_full)
print("   OK:", len(result_full), "filas")

print()
print("TODOS LOS PASOS COMPLETADOS SIN CRASH")
