from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

from utils.alegra_client import AlegraClient
from utils.validators import AlegraAPIError, TemplateError


class UploadAgent:
    """Agente 5: Sube la plantilla CSV a Alegra (masivo o individual como fallback)."""

    def __init__(self, client: AlegraClient | None = None):
        self.client = client or AlegraClient()

    # ─── Carga masiva ──────────────────────────────────────────────────────

    def upload_template(self, template_path: str) -> dict:
        """
        POST /journal-entries/import con el archivo CSV via multipart/form-data.
        Retorna la respuesta completa de Alegra.
        """
        path = Path(template_path)
        if not path.exists():
            raise FileNotFoundError(f"Plantilla no encontrada: {template_path}")

        logger.info(f"UploadAgent: iniciando carga masiva -> {path.name}")
        with open(path, "rb") as f:
            files = {"file": (path.name, f, "text/csv")}
            response = self.client.post_multipart("/journal-entries/import", files=files)

        logger.info(f"UploadAgent: respuesta de importación recibida.")
        return response if isinstance(response, dict) else {"raw": response}

    def verify_upload_result(self, upload_response: dict) -> dict:
        """Analiza la respuesta de Alegra post-importación y retorna resumen estructurado."""
        raw = upload_response

        # Alegra puede devolver distintas estructuras según versión
        total_processed = (
            raw.get("total", 0)
            or raw.get("totalProcessed", 0)
            or raw.get("processed", 0)
            or 0
        )
        successful = (
            raw.get("successful", 0)
            or raw.get("success", 0)
            or raw.get("created", 0)
            or 0
        )
        errors_raw = raw.get("errors", raw.get("failed", []))
        if isinstance(errors_raw, int):
            failed_count = errors_raw
            errors_list: list = []
        else:
            errors_list = errors_raw if isinstance(errors_raw, list) else []
            failed_count = len(errors_list)

        # IDs creados
        entries = raw.get("journalEntries", raw.get("data", raw.get("entries", [])))
        if isinstance(entries, list):
            journal_ids = [e.get("id") for e in entries if isinstance(e, dict) and e.get("id")]
        else:
            journal_ids = []

        overall_success = failed_count == 0 and (successful > 0 or total_processed > 0)

        result = {
            "success": overall_success,
            "total_processed": total_processed,
            "successful": successful,
            "failed": failed_count,
            "errors": errors_list,
            "journal_entry_ids": journal_ids,
        }

        if overall_success:
            logger.success(
                f"UploadAgent: carga exitosa — {successful} comprobantes creados."
            )
        else:
            logger.error(
                f"UploadAgent: {failed_count} errores en la importación. "
                f"Errores: {errors_list[:3]}"
            )
        return result

    # ─── Fallback individual ───────────────────────────────────────────────

    def fallback_individual_upload(self, template_df: pd.DataFrame) -> dict:
        """
        Sube cada comprobante individualmente agrupando por _numero_comprobante.
        Útil si la importación masiva falla.
        """
        logger.warning("UploadAgent: iniciando fallback de carga individual...")

        if "_numero_comprobante" not in template_df.columns:
            raise TemplateError("Columna '_numero_comprobante' requerida para fallback individual.")

        groups = list(template_df.groupby("_numero_comprobante"))
        total = len(groups)
        success_ids: list[int] = []
        failures: list[dict] = []

        for i, (numero, group) in enumerate(groups, 1):
            try:
                payload = self._build_journal_entry_payload(numero, group)
                response = self.client.post("/journal-entries", payload)
                entry_id = response.get("id") if isinstance(response, dict) else None
                success_ids.append(entry_id)
                logger.info(f"UploadAgent: [{i}/{total}] comprobante '{numero}' creado ID={entry_id}")
            except AlegraAPIError as exc:
                logger.error(f"UploadAgent: [{i}/{total}] fallo comprobante '{numero}' — {exc}")
                failures.append({"numero_comprobante": numero, "error": str(exc)})
            except Exception as exc:
                logger.error(f"UploadAgent: [{i}/{total}] error inesperado en '{numero}' — {exc}")
                failures.append({"numero_comprobante": numero, "error": str(exc)})

        summary = {
            "total": total,
            "successful": len(success_ids),
            "failed": len(failures),
            "journal_entry_ids": success_ids,
            "failures": failures,
        }
        logger.info(
            f"UploadAgent: fallback finalizado — "
            f"{len(success_ids)}/{total} exitosos, {len(failures)} fallos."
        )
        return summary

    def _build_journal_entry_payload(self, _numero: str, group: pd.DataFrame) -> dict:
        """Construye el payload JSON de un comprobante contable para POST /journal-entries."""
        first_row = group.iloc[0]
        items: list[dict] = []

        for _, row in group.iterrows():
            debit = float(row.get("debit", 0) or 0)
            credit = float(row.get("credit", 0) or 0)
            item: dict = {
                "account": {"id": row["account"]},
                "debit": debit,
                "credit": credit,
            }
            contact_val = row.get("contact")
            if contact_val and str(contact_val).strip():
                item["contact"] = {"id": contact_val}
            cost_center = row.get("costCenter", "")
            if cost_center and str(cost_center).strip():
                item["costCenter"] = {"id": cost_center}
            items.append(item)

        payload = {
            "date": str(first_row.get("date", "")),
            "description": str(first_row.get("description", "")),
            "observations": str(first_row.get("observations", "") or ""),
            "items": items,
        }
        return payload
