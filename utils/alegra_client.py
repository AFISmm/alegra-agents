from __future__ import annotations

import time
from typing import Any

import requests
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

import logging
from config import ALEGRA_USER, ALEGRA_TOKEN, ALEGRA_API_BASE, API_MAX_RETRIES, API_BACKOFF_BASE
from utils.validators import AlegraAPIError, AlegraConnectionError, AlegraRateLimitError


class AlegraClient:
    """Cliente HTTP reutilizable con auth, retry y rate-limit awareness."""

    def __init__(self):
        self.base_url = ALEGRA_API_BASE.rstrip("/")
        self._session: requests.Session | None = None

    def get_session(self) -> requests.Session:
        if self._session is None:
            session = requests.Session()
            session.auth = (ALEGRA_USER, ALEGRA_TOKEN)
            session.headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json",
            })
            self._session = session
        return self._session

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _safe_response_text(self, response: requests.Response) -> str:
        try:
            return response.text[:500]
        except Exception:
            return ""

    def _handle_response(self, response: requests.Response, url: str) -> Any:
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning(f"Rate limit alcanzado. Esperando {retry_after}s...")
            raise AlegraRateLimitError(
                "Rate limit excedido",
                status_code=429,
                url=url,
                response_body=self._safe_response_text(response),
            )
        if response.status_code >= 400:
            raise AlegraAPIError(
                f"Error HTTP {response.status_code}",
                status_code=response.status_code,
                url=url,
                response_body=self._safe_response_text(response),
            )
        try:
            return response.json()
        except Exception:
            return response.text

    @retry(
        retry=retry_if_exception_type(AlegraRateLimitError),
        stop=stop_after_attempt(API_MAX_RETRIES),
        wait=wait_exponential(multiplier=API_BACKOFF_BASE, min=2, max=120),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def get(self, endpoint: str, params: dict | None = None) -> Any:
        url = self._url(endpoint)
        logger.debug(f"GET {url} params={params}")
        try:
            resp = self.get_session().get(url, params=params, timeout=30)
        except requests.exceptions.ConnectionError as exc:
            raise AlegraConnectionError(f"Sin conexión a {url}: {exc}") from exc
        return self._handle_response(resp, url)

    @retry(
        retry=retry_if_exception_type(AlegraRateLimitError),
        stop=stop_after_attempt(API_MAX_RETRIES),
        wait=wait_exponential(multiplier=API_BACKOFF_BASE, min=2, max=120),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def post(self, endpoint: str, payload: dict | None = None) -> Any:
        url = self._url(endpoint)
        logger.debug(f"POST {url}")
        try:
            resp = self.get_session().post(url, json=payload, timeout=30)
        except requests.exceptions.ConnectionError as exc:
            raise AlegraConnectionError(f"Sin conexión a {url}: {exc}") from exc
        return self._handle_response(resp, url)

    def post_multipart(self, endpoint: str, files: dict, data: dict | None = None) -> Any:
        """POST multipart/form-data (para importación de archivos)."""
        url = self._url(endpoint)
        logger.debug(f"POST multipart {url}")
        session = self.get_session()
        # Quitar Content-Type para que requests lo genere con boundary
        headers = {k: v for k, v in session.headers.items() if k.lower() != "content-type"}
        try:
            resp = session.post(url, files=files, data=data, headers=headers, timeout=120)
        except requests.exceptions.ConnectionError as exc:
            raise AlegraConnectionError(f"Sin conexión a {url}: {exc}") from exc
        return self._handle_response(resp, url)

    def get_paginated(self, endpoint: str, params: dict | None = None) -> list:
        """Itera sobre todas las páginas de un endpoint y retorna lista completa."""
        params = params.copy() if params else {}
        params.setdefault("limit", 100)
        params["start"] = 0
        results: list = []

        while True:
            page = self.get(endpoint, params=params)

            if isinstance(page, list):
                if not page:
                    break
                results.extend(page)
                if len(page) < params["limit"]:
                    break
                params["start"] += len(page)
            elif isinstance(page, dict):
                items = page.get("data", page.get("items", []))
                if not items:
                    break
                results.extend(items)
                total = page.get("total", page.get("totalCount", 0))
                if total and len(results) >= total:
                    break
                if len(items) < params["limit"]:
                    break
                params["start"] += len(items)
            else:
                break

            time.sleep(0.1)  # cortesía entre páginas

        logger.debug(f"get_paginated({endpoint}): {len(results)} registros totales")
        return results
