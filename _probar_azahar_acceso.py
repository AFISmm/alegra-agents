import sys, json
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
logger.remove()
logger.add(sys.stdout, level="WARNING", format="{level} | {message}", colorize=False)

from utils.alegra_client import AlegraClient
client = AlegraClient()

AZAHAR_UUID = "2ec961b8-7784-4555-976d-a79031c78f65"

print("=" * 60)
print("PROBANDO ACCESO A AZAHAR RETAIL POR DISTINTOS METODOS")
print("=" * 60)

# Método 1: endpoint /companies/{uuid}
print("\n1. GET /companies/{uuid}...")
for ep in [f"/companies/{AZAHAR_UUID}", "/companies/Azahar+Retail+S.A.S"]:
    try:
        r = client.get(ep)
        print(f"   {ep}: OK →", json.dumps(r, ensure_ascii=False)[:150])
    except Exception as exc:
        print(f"   {ep}: {type(exc).__name__}: {str(exc)[:100]}")

# Método 2: encabezado X-Company o similar
print("\n2. GET /contacts con header X-Company-UUID...")
session = client.get_session()
original_headers = dict(session.headers)
try:
    session.headers["X-Company"] = AZAHAR_UUID
    import requests as _r
    resp = session.get(f"{client.base_url}/contacts", params={"limit": 2}, timeout=10)
    print(f"   Status: {resp.status_code} | Body: {resp.text[:200]}")
finally:
    session.headers.clear()
    session.headers.update(original_headers)

# Método 3: ver si /company devuelve info de otra empresa con parámetro
print("\n3. GET /company con params de empresa...")
for params in [{"company": AZAHAR_UUID}, {"uuid": AZAHAR_UUID}, {"id": "1"}]:
    try:
        r = client.get("/company", params=params)
        name = r.get("name", "?") if isinstance(r, dict) else str(r)[:60]
        print(f"   params={params}: empresa='{name}'")
    except Exception as exc:
        print(f"   params={params}: {type(exc).__name__}: {str(exc)[:80]}")

# Método 4: /user/me para ver si hay selección de empresa
print("\n4. GET /user/me o /users/me...")
for ep in ["/user/me", "/users/me", "/user", "/me"]:
    try:
        r = client.get(ep)
        print(f"   {ep}: OK →", json.dumps(r, ensure_ascii=False)[:200])
    except Exception as exc:
        print(f"   {ep}: {type(exc).__name__}: {str(exc)[:80]}")

print()
print("=" * 60)
print("CONCLUSION")
print("=" * 60)
print("Si ningún método cambia la empresa activa, la solución es:")
print("Ingresar a Alegra con el usuario propio de AZAHAR RETAIL")
print("y obtener el token API desde esa sesion.")
