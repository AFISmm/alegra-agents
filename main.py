"""
Punto de entrada del sistema de carga de comprobantes contables a Alegra.

Uso:
    python main.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

import config
from agents.orchestrator import Orchestrator


def setup_logging():
    """Configura loguru: consola + archivo rotado."""
    config.LOGS_FOLDER.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = config.LOGS_FOLDER / f"run_{ts}.log"

    import io
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    logger.remove()
    logger.add(
        sys.stderr,
        level=config.LOG_LEVEL,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        colorize=True,
    )
    logger.add(
        str(log_file),
        level="DEBUG",
        rotation="50 MB",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} | {message}",
    )
    logger.info(f"Log guardado en: {log_file}")


def validate_environment():
    """Verifica que las variables de entorno mínimas estén configuradas."""
    missing: list[str] = []
    if not config.ALEGRA_USER:
        missing.append("ALEGRA_USER")
    if not config.ALEGRA_TOKEN:
        missing.append("ALEGRA_TOKEN")
    if missing:
        logger.error(
            f"Variables de entorno faltantes: {missing}. "
            f"Copia .env.example a .env y completa los valores."
        )
        sys.exit(1)

    if not config.TRANSACTIONS_FOLDER.exists():
        logger.error(
            f"Carpeta de transacciones no encontrada: {config.TRANSACTIONS_FOLDER}. "
            f"Crea la carpeta o ajusta TRANSACTIONS_FOLDER en .env"
        )
        sys.exit(1)

    files = (
        list(config.TRANSACTIONS_FOLDER.glob("*.xlsx"))
        + list(config.TRANSACTIONS_FOLDER.glob("*.xls"))
        + list(config.TRANSACTIONS_FOLDER.glob("*.csv"))
    )
    if not files:
        logger.error(
            f"No hay archivos de transacciones en {config.TRANSACTIONS_FOLDER}. "
            f"Coloca los archivos xlsx/csv allí antes de ejecutar."
        )
        sys.exit(1)

    logger.info(f"Entorno validado — {len(files)} archivo(s) de transacciones encontrados.")


def main():
    setup_logging()
    logger.info("=" * 60)
    logger.info("SISTEMA DE CARGA DE COMPROBANTES CONTABLES — ALEGRA")
    logger.info("=" * 60)

    validate_environment()

    orchestrator = Orchestrator()
    result = orchestrator.run()

    if result.get("success"):
        logger.success("Proceso completado exitosamente.")
        sys.exit(0)
    else:
        logger.error("El proceso finalizó con errores. Revisa el reporte arriba.")
        sys.exit(1)


if __name__ == "__main__":
    main()
