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
print("BUSCANDO EMPRESAS CLIENTE DISPONIBLES EN LA CUENTA")
print("=" * 55)

# Verificar si hay endpoint de empresas gestionadas (multi-empresa)
endpoints_multi = [
    "/companies",
    "/organizations",
    "/clients/companies",
    "/accountant/companies",
]

for ep in endpoints_multi:
    try:
        r = client.get(ep)
        print(f"\nEndpoint {ep} respondio:")
        if isinstance(r, list):
            for item in r[:5]:
                print(f"  id={item.get('id')} | name={item.get('name')} | nit={item.get('identification','')}")
        elif isinstance(r, dict):
            print(f"  {r}")
    except Exception as exc:
        print(f"  {ep}: {type(exc).__name__}: {str(exc)[:80]}")

print()
print("=" * 55)
print("RESUMEN")
print("=" * 55)
print("Empresa activa: MERCURY METHODS LTDA (NIT 900188607)")
print()
print("Para operar sobre AZAHAR RETAIL S.A.S. necesitas:")
print("  1. El correo con el que AZAHAR esta registrada en Alegra")
print("  2. El token API de ESE usuario/empresa (no el de Mercury)")
print()
print("En Alegra, cada empresa tiene su propio usuario y token.")
print("Ve a: https://app.alegra.com/configuration/api")
print("pero iniciando sesion con la cuenta de AZAHAR RETAIL.")
