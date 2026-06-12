import sys, io, json
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()

from utils.alegra_client import AlegraClient
client = AlegraClient()
s = client.get_session()
base = client.base_url

print("=== Intentando variantes del endpoint ===")
print()

# Distintas variantes de URL y metodos
tests = [
    ("GET",  "/journal-entries"),
    ("GET",  "/journal-entries?limit=1"),
    ("POST", "/journal-entries"),           # Un POST minimo para ver si da otro error
    ("GET",  "/accounts?limit=1"),
    ("GET",  "/accounts?type=asset"),
    ("GET",  "/accounts?status=active"),
]

for method, ep in tests:
    url = base + ep
    if method == "GET":
        r = s.get(url, timeout=10)
    else:
        r = s.post(url, json={}, timeout=10)
    print(f"  {method} {ep} -> {r.status_code} | {r.text[:120]}")

print()
print("=== Probando API v2 ===")
base_v2 = base.replace("/v1", "/v2")
for ep in ["/journal-entries", "/accounts"]:
    r = s.get(base_v2 + ep, timeout=10)
    print(f"  {r.status_code} | {base_v2}{ep} | {r.text[:80]}")

print()
print("=== Comprobando si hay setup pendiente ===")
for ep in ["/accounting/setup", "/accounting/status", "/accounting/activate",
           "/journal-entries/setup", "/settings/accounting"]:
    r = s.get(base + ep, timeout=10)
    print(f"  {r.status_code} | {ep} | {r.text[:100]}")

print()
print("=== Headers Accept distintos en /journal-entries ===")
for accept in ["application/json", "text/plain", "*/*"]:
    r = s.get(base + "/journal-entries", headers={"Accept": accept}, timeout=10)
    print(f"  {r.status_code} | Accept: {accept}")
