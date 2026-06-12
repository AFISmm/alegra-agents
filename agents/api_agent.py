from __future__ import annotations

import requests
from loguru import logger

from utils.alegra_client import AlegraClient
from utils.validators import AlegraAPIError, AlegraConnectionError


class APIAgent:
    """Agente 1: Verifica credenciales y mantiene la sesión HTTP activa."""

    def __init__(self, client: AlegraClient | None = None):
        self.client = client or AlegraClient()

    def verify_connection(self) -> dict:
        """
        Hace GET /contacts?limit=1 como ping de verificación.
        Retorna dict de resultado. Lanza AlegraConnectionError si falla.
        """
        logger.info("APIAgent: verificando conexión con Alegra...")
        try:
            response = self.client.get("/contacts", params={"limit": 1})
            logger.success("APIAgent: conexión exitosa con Alegra.")
            return {
                "success": True,
                "status_code": 200,
                "message": "Conexión establecida correctamente",
                "user_info": {"user": self.client.get_session().auth[0]},
            }
        except AlegraConnectionError as exc:
            logger.error(f"APIAgent: fallo de conexión — {exc}")
            raise
        except AlegraAPIError as exc:
            logger.error(f"APIAgent: error de API — {exc}")
            raise AlegraConnectionError(
                f"Credenciales inválidas o error de autenticación: {exc}",
                status_code=exc.status_code,
                url=exc.url,
                response_body=exc.response_body,
            ) from exc
        except Exception as exc:
            logger.error(f"APIAgent: error inesperado — {exc}")
            raise AlegraConnectionError(f"Error inesperado al conectar: {exc}") from exc

    def get_authenticated_session(self) -> requests.Session:
        """Retorna la sesión autenticada y reutilizable."""
        return self.client.get_session()

    def test_rate_limit(self) -> bool:
        """
        Intenta un GET liviano; retorna True si está disponible, False si hay throttling.
        """
        try:
            self.client.get("/contacts", params={"limit": 1})
            return True
        except Exception:
            return False
