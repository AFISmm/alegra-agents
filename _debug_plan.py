import sys, io, json
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()

from utils.alegra_client import AlegraClient

client = AlegraClient()
session = client.get_session()

print("=== Informacion de empresa y plan ===")
print()

# Company info
resp = session.get(f"{client.base_url}/company", timeout=10)
if resp.status_code == 200:
    data = resp.json()
    print("EMPRESA:")
    print(f"  Nombre: {data.get('name')}")
    print(f"  Plan:   {data.get('plan', {})}")
    print(f"  Modulos: {data.get('modules', {})}")
    print()
    print("Estructura completa /company:")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])

print()
print("=== Settings ===")
resp2 = session.get(f"{client.base_url}/settings", timeout=10)
if resp2.status_code == 200:
    print(json.dumps(resp2.json(), ensure_ascii=False, indent=2)[:2000])

print()
print("=== Usuario actual ===")
resp3 = session.get(f"{client.base_url}/users/me", timeout=10)
print(f"  /users/me: {resp3.status_code}")
if resp3.status_code == 200:
    print(json.dumps(resp3.json(), ensure_ascii=False, indent=2)[:1000])

# Intentar variantes de journal entries
print()
print("=== Variantes journal-entries ===")
variants = [
    "/journal-entries?limit=1",
    "/accounting",
    "/accounting/journal",
    "/vouchers",
    "/ledger",
    "/general-journal",
]
for v in variants:
    r = session.get(f"{client.base_url}{v}", timeout=10)
    print(f"  {r.status_code} | {v}")
