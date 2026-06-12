import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
logger.remove()
logger.add(sys.stdout, level="WARNING", format="{level} | {message}", colorize=False)

from utils.alegra_client import AlegraClient

client = AlegraClient()

print("=" * 55)
print("VERIFICANDO EMPRESA ACTIVA EN ALEGRA")
print("=" * 55)

# Intentar obtener info de la empresa/organización
endpoints_to_try = [
    ("/company", "Información de empresa"),
    ("/organization", "Organización"),
    ("/user/company", "Usuario/empresa"),
    ("/settings/company", "Configuración empresa"),
]

for endpoint, label in endpoints_to_try:
    try:
        result = client.get(endpoint)
        print(f"\n{label} ({endpoint}):")
        if isinstance(result, dict):
            for k, v in result.items():
                if k in ("id", "name", "identification", "regime", "email", "phone", "address"):
                    print(f"  {k}: {v}")
        elif isinstance(result, list) and result:
            first = result[0]
            print(f"  (lista, primer elemento) id={first.get('id')} name={first.get('name')}")
        break
    except Exception as exc:
        print(f"  {label}: no disponible ({type(exc).__name__})")

# También probar GET /contacts?limit=1 para ver qué empresa responde
print()
print("Verificando contexto con GET /contacts...")
contacts = client.get("/contacts", params={"limit": 3})
if isinstance(contacts, list):
    print(f"Contactos encontrados: {len(contacts)}")
    for c in contacts[:3]:
        print(f"  id={c.get('id')} | name={c.get('name')} | nit={c.get('identification')}")
elif isinstance(contacts, dict):
    items = contacts.get("data", contacts.get("items", []))
    print(f"Contactos encontrados (dict): {len(items)}")
    for c in items[:3]:
        print(f"  id={c.get('id')} | name={c.get('name')} | nit={c.get('identification')}")
