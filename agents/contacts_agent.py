from __future__ import annotations

import pandas as pd
from loguru import logger

from utils.alegra_client import AlegraClient
from utils.validators import AlegraAPIError, ValidationError, validate_nit

CONTACT_TYPE_MAP = {
    "proveedor": "provider",
    "provider": "provider",
    "cliente": "client",
    "client": "client",
    "otro": "other",
    "other": "other",
}


class ContactsAgent:
    """Agente 2: Sincroniza terceros entre las transacciones y Alegra."""

    def __init__(self, client: AlegraClient | None = None):
        self.client = client or AlegraClient()

    def get_all_contacts_from_alegra(self) -> list[dict]:
        """Descarga todos los contactos de Alegra paginando."""
        logger.info("ContactsAgent: descargando todos los contactos de Alegra...")
        contacts = self.client.get_paginated("/contacts")
        logger.info(f"ContactsAgent: {len(contacts)} contactos obtenidos de Alegra.")
        return contacts

    def extract_contacts_from_transactions(self, transactions_df: pd.DataFrame) -> list[dict]:
        """Extrae terceros únicos del DataFrame de transacciones."""
        required_cols = {"nit_tercero", "nombre_tercero", "tipo_tercero"}
        missing = required_cols - set(transactions_df.columns)
        if missing:
            raise ValidationError(f"Columnas de terceros faltantes: {missing}")

        unique_rows = (
            transactions_df[["nit_tercero", "nombre_tercero", "tipo_tercero"]]
            .drop_duplicates(subset=["nit_tercero"])
            .reset_index(drop=True)
        )

        contacts = []
        for _, row in unique_rows.iterrows():
            nit_raw = str(row["nit_tercero"]).strip()
            # Saltar filas sin NIT (NIT vacío o '0' = sin tercero asignado)
            if not nit_raw or nit_raw == "0":
                continue
            try:
                nit = validate_nit(nit_raw)
                tipo_raw = str(row["tipo_tercero"]).strip().lower()
                tipo = CONTACT_TYPE_MAP.get(tipo_raw, "other")
                contacts.append({
                    "identification": nit,
                    "name": str(row["nombre_tercero"]).strip(),
                    "type": tipo,
                })
            except ValidationError as exc:
                logger.warning(f"ContactsAgent: NIT inválido ignorado — {exc}")

        logger.info(f"ContactsAgent: {len(contacts)} terceros únicos en las transacciones.")
        return contacts

    def find_missing_contacts(self, required: list[dict], existing: list[dict]) -> list[dict]:
        """Retorna los contactos requeridos que no existen en Alegra (match por NIT)."""
        existing_nits = {
            str(c.get("identification", "")).replace(".", "").replace("-", "")
            for c in existing
            if c.get("identification")
        }
        missing = [c for c in required if c["identification"] not in existing_nits]
        logger.info(
            f"ContactsAgent: {len(missing)} terceros por crear "
            f"(de {len(required)} requeridos, {len(existing)} existentes)."
        )
        return missing

    def create_contact(self, contact: dict) -> dict:
        """Crea un contacto en Alegra. Retorna el contacto con su ID asignado."""
        nit = contact["identification"]
        payload = {
            "name": contact["name"],
            "identification": nit,
            "type": [contact["type"]],
            "kindOfPerson": "LEGAL_ENTITY",
            "identificationObject": {
                "type": "NIT",
                "number": nit,
            },
        }
        logger.debug(f"ContactsAgent: creando contacto NIT={nit}...")
        result = self.client.post("/contacts", payload)
        logger.success(
            f"ContactsAgent: contacto creado — NIT={contact['identification']} ID={result.get('id')}"
        )
        return result

    def ensure_all_contacts_exist(self, transactions_df: pd.DataFrame) -> dict:
        """
        Orquesta: extrae → descarga existentes → compara → crea faltantes.
        Retorna resumen con contacts_map (NIT -> alegra_id).
        """
        required = self.extract_contacts_from_transactions(transactions_df)
        existing = self.get_all_contacts_from_alegra()

        contacts_map: dict[str, int] = {}
        for c in existing:
            nit = str(c.get("identification", "")).replace(".", "").replace("-", "")
            if nit:
                contacts_map[nit] = c.get("id")

        missing = self.find_missing_contacts(required, existing)

        created_count = 0
        failed: list[dict] = []

        for contact in missing:
            try:
                new_contact = self.create_contact(contact)
                nit = contact["identification"]
                contacts_map[nit] = new_contact.get("id")
                created_count += 1
            except (AlegraAPIError, Exception) as exc:
                logger.error(
                    f"ContactsAgent: fallo al crear contacto NIT={contact['identification']} — {exc}"
                )
                failed.append({"contact": contact, "error": str(exc)})

        already_existed = len(required) - len(missing)
        summary = {
            "total_required": len(required),
            "already_existed": already_existed,
            "created": created_count,
            "failed": failed,
            "contacts_map": contacts_map,
        }
        logger.info(
            f"ContactsAgent: resumen — requeridos={len(required)}, "
            f"existentes={already_existed}, creados={created_count}, fallidos={len(failed)}"
        )
        return summary
