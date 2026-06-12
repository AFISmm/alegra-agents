from __future__ import annotations


class AlegraAPIError(Exception):
    """Error en la comunicación con la API de Alegra."""

    def __init__(self, message: str, status_code: int = 0, url: str = "", response_body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.response_body = response_body

    def __str__(self) -> str:
        base = super().__str__()
        parts = [base]
        if self.status_code:
            parts.append(f"HTTP {self.status_code}")
        if self.url:
            parts.append(f"URL: {self.url}")
        if self.response_body:
            parts.append(f"Response: {self.response_body[:300]}")
        return " | ".join(parts)


class AlegraConnectionError(AlegraAPIError):
    """No se puede establecer conexión con Alegra."""


class AlegraRateLimitError(AlegraAPIError):
    """Se excedió el rate limit de la API."""


class ValidationError(Exception):
    """Error de validación de datos de entrada."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class TemplateError(Exception):
    """Error al generar o procesar la plantilla de comprobantes."""

    def __init__(self, message: str, row_errors: list | None = None):
        super().__init__(message)
        self.row_errors = row_errors or []


def validate_nit(nit: str) -> str:
    """Limpia y valida un NIT colombiano. Retorna solo dígitos."""
    if not nit:
        raise ValidationError("NIT vacío o nulo")
    cleaned = str(nit).strip().replace(".", "").replace("-", "").replace(" ", "")
    if not cleaned.isdigit():
        raise ValidationError(f"NIT inválido: '{nit}' — debe contener solo dígitos")
    return cleaned


def validate_account_code(code: str) -> str:
    """Valida que el código de cuenta sea numérico y tenga formato PUC."""
    if not code:
        raise ValidationError("Código de cuenta vacío")
    cleaned = str(code).strip()
    if not cleaned.isdigit():
        raise ValidationError(f"Código de cuenta inválido: '{code}'")
    return cleaned


def validate_amount(value) -> float:
    """Convierte un valor a float con 2 decimales. Lanza error si no es numérico."""
    try:
        result = round(float(str(value).replace(",", "").replace(" ", "")), 2)
        if result < 0:
            raise ValidationError(f"Monto negativo no permitido: {value}")
        return result
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"Monto inválido: '{value}'") from exc


def validate_date(value) -> str:
    """Convierte una fecha al formato ISO YYYY-MM-DD.

    Usa datetime estándar (no pandas) para evitar crashes con pd.to_datetime
    en Python 3.14+.
    """
    from datetime import datetime

    s = str(value).strip()[:10]  # tomar solo YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValidationError(f"Fecha inválida: '{value}'")
