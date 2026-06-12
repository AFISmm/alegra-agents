import sys, json, io
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
logger.remove()
logger.add(sys.stdout, level="WARNING", format="{level} | {message}", colorize=False)

from utils.alegra_client import AlegraClient
client = AlegraClient()

print("=== Probando distintos payloads para POST /contacts ===")
print()

# Ver primero como luce un contacto existente para copiar su estructura
existing = client.get("/contacts", params={"limit": 1})
if existing:
    print("Estructura de contacto existente (Consumidor Final):")
    print(json.dumps(existing[0] if isinstance(existing, list) else existing, indent=2, ensure_ascii=False))
    print()

# Intentos en orden de complejidad
payloads = [
    # 1. Solo name
    {"name": "PRUEBA TEST NIT"},

    # 2. name + identification como string
    {"name": "PRUEBA TEST NIT", "identification": "900583993"},

    # 3. Con kindOfPerson
    {"name": "PRUEBA TEST NIT", "identification": "900583993", "kindOfPerson": "LEGAL_ENTITY"},

    # 4. Con identificationObject (formato NIT colombiano)
    {
        "name": "PRUEBA TEST NIT",
        "identificationObject": {
            "type": "NIT",
            "number": "900583993",
        },
        "kindOfPerson": "LEGAL_ENTITY",
    },

    # 5. Solo name y type como string (no array)
    {"name": "PRUEBA TEST NIT", "identification": "900583993", "type": "other"},

    # 6. Con phonePrimary (a veces requerido)
    {"name": "PRUEBA TEST NIT", "identification": "900583993", "type": ["other"]},
]

for i, payload in enumerate(payloads, 1):
    print(f"Intento {i}: {json.dumps(payload, ensure_ascii=False)}")
    try:
        result = client.post("/contacts", payload)
        print(f"  OK: id={result.get('id')} name={result.get('name')}")
        # Si se creo, eliminarlo para no ensuciar
        contact_id = result.get("id")
        if contact_id:
            try:
                client.get_session().delete(
                    f"{client.base_url}/contacts/{contact_id}", timeout=10
                )
                print(f"  (contacto prueba eliminado)")
            except Exception:
                pass
        break  # Parar en el primer que funcione
    except Exception as exc:
        print(f"  FALLO: {str(exc)[:120]}")
    print()
