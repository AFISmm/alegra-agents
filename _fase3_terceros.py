import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

import io
from loguru import logger
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logger.remove()
logger.add(sys.stdout, level="INFO", format="{level:<8} | {message}", colorize=False)

print("=" * 60)
print("FASE 3: VERIFICACION Y SINCRONIZACION DE TERCEROS")
print("=" * 60)

from agents.template_agent import TemplateAgent
from agents.contacts_agent import ContactsAgent

template_agent = TemplateAgent()
df = template_agent.read_transaction_files("data/transactions")
print(f"\nTransacciones cargadas: {len(df)} filas")

contacts_agent = ContactsAgent()
required = contacts_agent.extract_contacts_from_transactions(df)
print(f"Terceros requeridos (con NIT): {len(required)}")

print("\nDescargando contactos existentes en Alegra Azahar...")
existing = contacts_agent.get_all_contacts_from_alegra()
print(f"Contactos existentes en Alegra: {len(existing)}")

missing = contacts_agent.find_missing_contacts(required, existing)

existing_nits = {
    str(e.get("identification", "")).replace(".", "").replace("-", "")
    for e in existing if e.get("identification")
}

print()
print("--- Estado de terceros ---")
for c in required:
    estado = "YA EXISTE" if c["identification"] in existing_nits else "FALTA"
    print(f"  [{estado:<10}] NIT: {c['identification']:<12} | {c['name']}")

if not missing:
    print("\nTodos los terceros ya existen. Nada que crear.")
    sys.exit(0)

print(f"\n{len(missing)} tercero(s) seran creados en Alegra Azahar...")
print()

result = contacts_agent.ensure_all_contacts_exist(df)

print()
print("=" * 60)
print("RESULTADO FASE 3")
print("=" * 60)
print(f"  Requeridos : {result['total_required']}")
print(f"  Existian   : {result['already_existed']}")
print(f"  Creados    : {result['created']}")
print(f"  Fallidos   : {len(result['failed'])}")

if result["failed"]:
    print()
    print("  ERRORES:")
    for f in result["failed"]:
        print(f"    NIT {f['contact']['identification']}: {f['error']}")

print()
print(f"  Mapa NIT->ID Alegra ({len(result['contacts_map'])} entradas):")
for nit, aid in result["contacts_map"].items():
    print(f"    {nit} -> ID {aid}")

if len(result["failed"]) == 0:
    print()
    print("FASE 3: OK - Todos los terceros listos")
else:
    print()
    print("FASE 3: WARN - Algunos terceros fallaron, revisar errores arriba")
