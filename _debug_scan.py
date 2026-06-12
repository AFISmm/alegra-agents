import sys, io
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()

from utils.alegra_client import AlegraClient
client = AlegraClient()
s = client.get_session()
base = client.base_url  # https://api.alegra.com/api/v1

candidates = [
    # Variantes de journal entries
    "/journal-entries",
    "/journalentries",
    "/journal_entries",
    "/comprobantes",
    "/comprobantes-contables",
    "/accounting-entries",
    "/accounting-vouchers",
    "/vouchers",
    "/ledger-entries",
    "/ledger",
    "/general-journal",
    "/entries",
    # Variantes de accounts / chart of accounts
    "/accounts",
    "/chart-of-accounts",
    "/ledger-accounts",
    "/account-categories",
    "/cuentas",
    # Raices de módulo
    "/accounting",
    "/contabilidad",
    "/bookkeeping",
    # Sub-paths contables
    "/accounting/journal-entries",
    "/accounting/accounts",
    "/accounting/entries",
    # Prefijos colombia
    "/col/journal-entries",
    "/co/journal-entries",
]

print(f"Escaneando {len(candidates)} endpoints en {base}")
print()

ok, forbidden, notfound, other = [], [], [], []
for ep in candidates:
    try:
        r = s.get(base + ep, params={"limit": 1}, timeout=8)
        code = r.status_code
        if code == 200:
            ok.append((ep, r.text[:80]))
        elif code == 403:
            forbidden.append(ep)
        elif code == 404:
            notfound.append(ep)
        else:
            other.append((ep, code, r.text[:60]))
    except Exception as exc:
        other.append((ep, "ERR", str(exc)[:60]))

print(f"OK (200): {len(ok)}")
for ep, body in ok:
    print(f"  {ep} -> {body}")

print(f"\nForbidden (403): {len(forbidden)}")
for ep in forbidden:
    print(f"  {ep}")

print(f"\nNot found (404): {len(notfound)}")
for ep in notfound:
    print(f"  {ep}")

print(f"\nOtros: {len(other)}")
for ep, code, body in other:
    print(f"  {code} | {ep} | {body}")
