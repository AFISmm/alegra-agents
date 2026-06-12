print("LINE 1 - inicio")
import sys
print("LINE 2 - sys ok")
sys.path.insert(0, ".")
print("LINE 3 - path ok")

import warnings
warnings.filterwarnings("ignore")
print("LINE 4 - warnings ok")

from loguru import logger
print("LINE 5 - loguru ok")
logger.remove()
logger.add(sys.stdout, level="WARNING", format="{level} | {message}", colorize=False)
print("LINE 6 - logger configurado")

import pandas as pd
print("LINE 7 - pandas ok", pd.__version__)

from utils.siigo_parser import parse_siigo_auxiliary
print("LINE 8 - siigo_parser importado")

print("LINE 9 - llamando parse_siigo_auxiliary...")
df = parse_siigo_auxiliary("data/transactions/AUXILIAR 2016 - DIC.xlsx")
print("LINE 10 - parse OK, filas:", len(df))

print("LINE 11 - construyendo lookups...")
accounts_lookup = {str(c).strip(): {"id": str(c).strip()} for c in df["codigo_cuenta"].unique()}
contacts_map = {n: n for n in df["nit_tercero"].unique() if str(n).strip()}
print("LINE 12 - lookups OK. cuentas:", len(accounts_lookup), "contactos:", len(contacts_map))

from utils.validators import validate_date, validate_amount
print("LINE 13 - validators ok")

print("LINE 14 - probando validate_date con primera fecha...")
primera_fecha = df.iloc[0]["fecha"]
print("   valor:", repr(primera_fecha))
resultado = validate_date(primera_fecha)
print("LINE 15 - validate_date OK:", resultado)

print("LINE 16 - probando validate_amount...")
resultado2 = validate_amount(df.iloc[0]["debito"])
print("LINE 17 - validate_amount OK:", resultado2)

print("DONE - sin crash")
