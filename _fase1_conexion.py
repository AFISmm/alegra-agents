import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
logger.remove()
logger.add(sys.stdout, level="INFO", format="{level:<8} | {message}", colorize=False)

print("=" * 55)
print("FASE 1: VERIFICACION DE CONEXION CON ALEGRA API")
print("=" * 55)

from agents.api_agent import APIAgent
from utils.validators import AlegraConnectionError

agent = APIAgent()

try:
    result = agent.verify_connection()
    print()
    print("RESULTADO:")
    print("  Conexion exitosa :", result["success"])
    print("  HTTP status      :", result["status_code"])
    print("  Mensaje          :", result["message"])
    print("  Usuario          :", result["user_info"].get("user", ""))
    print()
    print("FASE 1: OK - Podemos continuar")
except AlegraConnectionError as exc:
    print()
    print("FASE 1: FALLO -", exc)
    sys.exit(1)
except Exception as exc:
    print()
    print("FASE 1: ERROR INESPERADO -", exc)
    sys.exit(1)
