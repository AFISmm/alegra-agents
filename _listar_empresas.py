import sys, json
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
logger.remove()
logger.add(sys.stdout, level="WARNING", format="{level} | {message}", colorize=False)

from utils.alegra_client import AlegraClient
client = AlegraClient()

print("=" * 55)
print("EMPRESAS DISPONIBLES EN LA CUENTA")
print("=" * 55)

companies = client.get("/companies")

print(f"Total empresas: {len(companies) if isinstance(companies, list) else 'N/A'}")
print()

if isinstance(companies, list):
    for i, c in enumerate(companies):
        print(f"--- Empresa {i+1} ---")
        print(json.dumps(c, indent=2, ensure_ascii=False))
        print()
elif isinstance(companies, dict):
    print(json.dumps(companies, indent=2, ensure_ascii=False))
