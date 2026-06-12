from __future__ import annotations

import pandas as pd
from loguru import logger

from utils.alegra_client import AlegraClient
from utils.validators import ValidationError, validate_account_code

# Tipos de cuenta del PUC colombiano y su naturaleza (D=débito, C=crédito)
PUC_NATURE: dict[str, str] = {
    "1": "D",  # Activos
    "2": "C",  # Pasivos
    "3": "C",  # Patrimonio
    "4": "C",  # Ingresos
    "5": "D",  # Gastos
    "6": "D",  # Costos de ventas
    "7": "D",  # Costos de producción
}


class ChartOfAccountsAgent:
    """Agente 3: Descarga y verifica el plan de cuentas contra las transacciones."""

    def __init__(self, client: AlegraClient | None = None):
        self.client = client or AlegraClient()

    def get_full_chart_of_accounts(self) -> list[dict]:
        """Descarga el plan de cuentas completo de Alegra."""
        logger.info("ChartOfAccountsAgent: descargando plan de cuentas...")
        accounts = self.client.get_paginated("/accounts")
        logger.info(f"ChartOfAccountsAgent: {len(accounts)} cuentas descargadas.")
        return accounts

    def build_accounts_lookup(self, accounts: list[dict]) -> dict[str, dict]:
        """
        Construye dict de búsqueda rápida por código de cuenta.
        Solo incluye cuentas activas.
        """
        lookup: dict[str, dict] = {}
        for account in accounts:
            is_active = account.get("isActive", True)
            status = str(account.get("status", "active")).lower()
            if is_active and status in ("active", "activo", "activa"):
                code = str(account.get("code", "")).strip()
                if code:
                    lookup[code] = account
        logger.debug(f"ChartOfAccountsAgent: {len(lookup)} cuentas activas en lookup.")
        return lookup

    def verify_accounts_in_transactions(
        self,
        transactions_df: pd.DataFrame,
        accounts_lookup: dict[str, dict],
    ) -> dict:
        """Verifica que cada código de cuenta en las transacciones existe y está activo."""
        if "codigo_cuenta" not in transactions_df.columns:
            raise ValidationError("Columna 'codigo_cuenta' no encontrada en transacciones.")

        # Obtener set de todos los códigos referenciados
        referenced_codes = set(
            str(c).strip() for c in transactions_df["codigo_cuenta"].dropna().unique()
        )

        # Obtener también las cuentas inactivas para distinguir faltante vs inactiva
        all_accounts_raw = self.client.get_paginated("/accounts")
        all_codes: dict[str, dict] = {
            str(a.get("code", "")).strip(): a
            for a in all_accounts_raw
            if a.get("code")
        }

        accounts_found: list[str] = []
        accounts_missing: list[str] = []
        accounts_inactive: list[str] = []

        for code in sorted(referenced_codes):
            if code in accounts_lookup:
                accounts_found.append(code)
            elif code in all_codes:
                accounts_inactive.append(code)
            else:
                accounts_missing.append(code)

        valid = not accounts_missing and not accounts_inactive
        result = {
            "valid": valid,
            "total_accounts_referenced": len(referenced_codes),
            "accounts_found": accounts_found,
            "accounts_missing": accounts_missing,
            "accounts_inactive": accounts_inactive,
        }

        if accounts_missing:
            logger.error(
                f"ChartOfAccountsAgent: {len(accounts_missing)} cuentas NO existen en Alegra: "
                f"{accounts_missing}"
            )
        if accounts_inactive:
            logger.error(
                f"ChartOfAccountsAgent: {len(accounts_inactive)} cuentas INACTIVAS: "
                f"{accounts_inactive}"
            )
        if valid:
            logger.success(
                f"ChartOfAccountsAgent: todas las {len(accounts_found)} cuentas verificadas."
            )

        return result

    def validate_account_types(
        self,
        transactions_df: pd.DataFrame,
        accounts_lookup: dict[str, dict],
    ) -> list[dict]:
        """
        Verifica que las cuentas débito/crédito tienen naturaleza correcta según PUC.
        Retorna lista de inconsistencias (puede estar vacía si todo está OK).
        """
        inconsistencies: list[dict] = []

        for _, row in transactions_df.iterrows():
            code = str(row.get("codigo_cuenta", "")).strip()
            debit = float(row.get("debito", 0) or 0)
            credit = float(row.get("credito", 0) or 0)

            if not code or code not in accounts_lookup:
                continue

            first_digit = code[0] if code else ""
            expected_nature = PUC_NATURE.get(first_digit)
            if not expected_nature:
                continue

            if expected_nature == "D" and credit > 0 and debit == 0:
                inconsistencies.append({
                    "row": row.name,
                    "account": code,
                    "issue": f"Cuenta {code} es de naturaleza DÉBITO pero tiene movimiento crédito",
                })
            elif expected_nature == "C" and debit > 0 and credit == 0:
                inconsistencies.append({
                    "row": row.name,
                    "account": code,
                    "issue": f"Cuenta {code} es de naturaleza CRÉDITO pero tiene movimiento débito",
                })

        if inconsistencies:
            logger.warning(
                f"ChartOfAccountsAgent: {len(inconsistencies)} posibles inconsistencias de tipo de cuenta."
            )
        return inconsistencies
