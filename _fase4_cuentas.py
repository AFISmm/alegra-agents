import sys, io
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
logger.remove()
logger.add(sys.stdout, level="INFO", format="{level:<8} | {message}", colorize=False)

print("=" * 60)
print("FASE 4: VERIFICACION DEL PLAN DE CUENTAS (AZAHAR RETAIL)")
print("=" * 60)

from agents.template_agent import TemplateAgent
from agents.chart_of_accounts_agent import ChartOfAccountsAgent

template_agent = TemplateAgent()
df = template_agent.read_transaction_files("data/transactions")
print(f"\nTransacciones cargadas: {len(df)} filas")

codigos_usados = sorted(df["codigo_cuenta"].dropna().unique().tolist())
print(f"Codigos de cuenta en el archivo: {len(codigos_usados)}")
for c in codigos_usados:
    print(f"  {c}")

print()
print("Descargando plan de cuentas de Alegra Azahar...")
agent = ChartOfAccountsAgent()
alegra_accounts = agent.get_full_chart_of_accounts()
accounts_lookup = agent.build_accounts_lookup(alegra_accounts)
print(f"Cuentas activas en Alegra: {len(accounts_lookup)}")

result = agent.verify_accounts_in_transactions(df, accounts_lookup)

print()
print("--- Verificacion de cuentas ---")
for code in result["accounts_found"]:
    acc = accounts_lookup[code]
    print(f"  [OK      ] {code} -> ID={acc['id']} | {acc.get('name', '')[:40]}")
for code in result["accounts_inactive"]:
    print(f"  [INACTIVA] {code}")
for code in result["accounts_missing"]:
    print(f"  [FALTA   ] {code}")

print()
print("=" * 60)
print("RESULTADO FASE 4")
print("=" * 60)
print(f"  Total cuentas referenciadas : {result['total_accounts_referenced']}")
print(f"  Encontradas                 : {len(result['accounts_found'])}")
print(f"  Inactivas                   : {len(result['accounts_inactive'])}")
print(f"  Faltantes                   : {len(result['accounts_missing'])}")

if result["valid"]:
    print()
    print("FASE 4: OK - Todas las cuentas verificadas en Alegra.")
else:
    print()
    print("FASE 4: ERROR - Hay cuentas faltantes o inactivas.")
    if result["accounts_missing"]:
        print("  Las siguientes cuentas deben crearse en Alegra:")
        for c in result["accounts_missing"]:
            print(f"    {c}")
