import sys, io, json
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()

from utils.alegra_client import AlegraClient

client = AlegraClient()
session = client.get_session()

# Explorar todos los endpoints principales de Alegra API v1
endpoints = [
    "/company",
    "/users",
    "/contacts",
    "/items",
    "/invoices",
    "/bills",
    "/payments",
    "/expenses",
    "/bank-accounts",
    "/taxes",
    "/categories",
    "/price-lists",
    "/warehouses",
    "/cost-centers",
    "/journal-entries",
    "/journal-entries/import",
    "/accounting/journal-entries",
    "/accounts",
    "/chart-of-accounts",
    "/settings",
]

print("=== Endpoints accesibles con el token actual ===")
print()
for ep in endpoints:
    url = f"{client.base_url}{ep}"
    try:
        resp = session.get(url, timeout=10)
        status = resp.status_code
        if status == 200:
            data = resp.json()
            count = len(data) if isinstance(data, list) else "dict"
            print(f"  OK  {status} | {ep}  ({count})")
        elif status == 405:
            print(f"  ??? {status} | {ep}  (Method Not Allowed - existe)")
        elif status in (400, 404):
            print(f"  --- {status} | {ep}")
        else:
            print(f"  !!! {status} | {ep}")
    except Exception as exc:
        print(f"  ERR       | {ep}: {exc}")

print()
print("=== Detalle de /cost-centers y /journal-entries ===")
for ep in ["/cost-centers", "/journal-entries"]:
    url = f"{client.base_url}{ep}"
    resp = session.get(url, params={"limit": 3}, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        print(f"\n{ep}:")
        if isinstance(data, list) and data:
            print(json.dumps(data[0], ensure_ascii=False, indent=2)[:600])
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2)[:600])
    else:
        print(f"{ep}: {resp.status_code}")
