import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

ALEGRA_USER = os.getenv("ALEGRA_USER", "")
ALEGRA_TOKEN = os.getenv("ALEGRA_TOKEN", "")
ALEGRA_API_BASE = os.getenv("ALEGRA_API_BASE", "https://api.alegra.com/api/v1")

TRANSACTIONS_FOLDER = BASE_DIR / os.getenv("TRANSACTIONS_FOLDER", "data/transactions")
TEMPLATES_OUTPUT_FOLDER = BASE_DIR / os.getenv("TEMPLATES_OUTPUT_FOLDER", "data/templates")
LOGS_FOLDER = BASE_DIR / "data" / "logs"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Paginación y rate limiting
API_PAGE_SIZE = 100
API_MAX_RETRIES = 5
API_BACKOFF_BASE = 2        # segundos base para backoff exponencial
API_RATE_LIMIT_PER_MIN = 100

# Columnas requeridas en archivos de transacciones de entrada
REQUIRED_TRANSACTION_COLUMNS = [
    "fecha",
    "descripcion",
    "nit_tercero",
    "nombre_tercero",
    "tipo_tercero",
    "codigo_cuenta",
    "nombre_cuenta",
    "debito",
    "credito",
    "numero_comprobante",
]

# Columnas opcionales
OPTIONAL_TRANSACTION_COLUMNS = ["centro_costo", "observaciones"]

# Columnas de la plantilla de salida para Alegra
ALEGRA_TEMPLATE_COLUMNS = [
    "date",
    "description",
    "account",
    "debit",
    "credit",
    "contact",
    "costCenter",
    "observations",
]
