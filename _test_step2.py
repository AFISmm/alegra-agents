import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Silenciar loguru para la prueba — solo stdout
from loguru import logger as _logger
_logger.remove()
_logger.add(sys.stdout, level="INFO", format="{level} | {message}", colorize=False)

from agents.template_agent import TemplateAgent
from agents.contacts_agent import ContactsAgent

agent = TemplateAgent()
df = agent.read_transaction_files("data/transactions")

print("=" * 60)
print("PASO 2B: CONTACTOS A SINCRONIZAR CON ALEGRA")
print("=" * 60)
ca = ContactsAgent()
contacts = ca.extract_contacts_from_transactions(df)
print("Total terceros unicos con NIT:", len(contacts))
print()
for c in contacts:
    print("  NIT:", c["identification"].ljust(15), "tipo:", c["type"].ljust(10), "nombre:", c["name"])

print()
print("=" * 60)
print("PASO 2C: VERIFICACION DE COLUMNAS")
print("=" * 60)
col_check = agent.validate_required_columns(df)
print("Valido:", col_check["valid"])
print("Faltantes:", col_check["missing_columns"])

print()
print("=" * 60)
print("PASO 2D: TRANSFORMACION A FORMATO ALEGRA (con cuentas/contactos ficticios)")
print("=" * 60)

accounts_lookup = {}
for code in df["codigo_cuenta"].unique():
    accounts_lookup[str(code).strip()] = {"id": str(code).strip(), "code": str(code).strip()}

contacts_map = {}
for c in contacts:
    contacts_map[c["identification"]] = c["identification"]

try:
    template_df = agent.transform_to_alegra_format(df, contacts_map, accounts_lookup)
except Exception as exc:
    import traceback
    print("ERROR en transform_to_alegra_format:")
    traceback.print_exc()
    sys.exit(1)
print("Filas en plantilla:", len(template_df))
print("Columnas:", list(template_df.columns))
print()
print("Primeras 8 filas:")
cols = ["date", "description", "account", "debit", "credit", "contact", "costCenter", "_numero_comprobante"]
print(template_df[cols].head(8).to_string())

print()
print("=" * 60)
print("PASO 2E: VALIDACION COMPLETITUD DE PLANTILLA")
print("=" * 60)
completeness = agent.validate_template_completeness(template_df)
print("Valida:", completeness["valid"])
print("Total filas:", completeness["total_rows"])
print("Filas con errores:", len(completeness["rows_with_errors"]))
if completeness["rows_with_errors"]:
    print("Detalle errores:", completeness["error_detail"])

print()
print("=" * 60)
print("PASO 2F: EXPORTACION CSV")
print("=" * 60)
output_path = agent.export_template(template_df, "data/templates")
print("Archivo generado:", output_path)

import pandas as pd
exported = pd.read_csv(output_path, encoding="utf-8-sig")
print("Filas exportadas:", len(exported))
print("Columnas CSV:", list(exported.columns))
print()
print("Primeras 5 filas del CSV:")
print(exported.head(5).to_string())
