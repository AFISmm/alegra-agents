from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from config import TRANSACTIONS_FOLDER, TEMPLATES_OUTPUT_FOLDER, LOGS_FOLDER
from utils.alegra_client import AlegraClient
from utils.validators import AlegraConnectionError, ValidationError, TemplateError
from agents.api_agent import APIAgent
from agents.contacts_agent import ContactsAgent
from agents.chart_of_accounts_agent import ChartOfAccountsAgent
from agents.template_agent import TemplateAgent
from agents.upload_agent import UploadAgent

PHASE_STATUS_OK = "OK"
PHASE_STATUS_WARN = "WARN"
PHASE_STATUS_FAILED = "FAILED"
PHASE_STATUS_SKIPPED = "SKIPPED"
PHASE_STATUS_BLOCKED = "BLOCKED"


class Orchestrator:
    """Agente 6: Coordina el flujo completo de carga de comprobantes a Alegra."""

    def __init__(self):
        self.client = AlegraClient()
        self.api_agent = APIAgent(self.client)
        self.contacts_agent = ContactsAgent(self.client)
        self.coa_agent = ChartOfAccountsAgent(self.client)
        self.template_agent = TemplateAgent()
        self.upload_agent = UploadAgent(self.client)

        self.phase_results: dict[str, dict] = {}
        self.start_time: float = 0.0
        self._run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Estado de datos entre fases
        self._transactions_df = None
        self._contacts_map: dict = {}
        self._accounts_lookup: dict = {}
        self._template_path: str = ""
        self._template_df = None

    # ─── Método principal ─────────────────────────────────────────────────

    def run(self) -> dict:
        self.start_time = time.time()
        logger.info("=" * 60)
        logger.info("INICIANDO PROCESO DE CARGA DE COMPROBANTES A ALEGRA")
        logger.info("=" * 60)

        # ── FASE 1: Conexión API ──────────────────────────────────────────
        result = self._run_phase(1, "Conexión API", self.api_agent.verify_connection)
        if result["status"] == PHASE_STATUS_FAILED:
            return self._abort("Fase 1 fallida: sin conexión a la API de Alegra.")

        # ── FASE 2: Lectura de transacciones ─────────────────────────────
        result = self._run_phase(2, "Lectura de Transacciones", self._fase2_leer_transacciones)
        if result["status"] == PHASE_STATUS_FAILED:
            return self._abort("Fase 2 fallida: errores en los archivos de transacciones.")

        # ── FASE 3: Verificación de terceros ─────────────────────────────
        result = self._run_phase(
            3, "Verificación de Terceros",
            self.contacts_agent.ensure_all_contacts_exist,
            self._transactions_df,
        )
        if result["status"] == PHASE_STATUS_FAILED:
            return self._abort("Fase 3 fallida: error crítico en terceros.")
        if result["status"] == PHASE_STATUS_WARN:
            logger.warning("Fase 3: algunos terceros fallaron. Continuando con los disponibles.")
        self._contacts_map = result.get("data", {}).get("contacts_map", {})

        # ── FASE 4: Verificación plan de cuentas ─────────────────────────
        result = self._run_phase(4, "Plan de Cuentas", self._fase4_verificar_cuentas)
        if result["status"] == PHASE_STATUS_FAILED:
            return self._abort("Fase 4 fallida: cuentas contables faltantes o inactivas.")

        # ── FASE 5: Generación de plantilla ──────────────────────────────
        result = self._run_phase(5, "Generación de Plantilla", self._fase5_generar_plantilla)
        if result["status"] == PHASE_STATUS_FAILED:
            return self._abort("Fase 5 fallida: errores en la plantilla de comprobantes.")

        # ── FASE 6: Gate de seguridad pre-carga ──────────────────────────
        result = self._run_phase(6, "Validación Pre-Carga (Gate)", self._validate_pre_upload_checklist)
        if result["status"] == PHASE_STATUS_BLOCKED:
            return self._abort("Fase 6 bloqueada: checklist pre-carga no aprobado.")

        # ── FASE 7: Carga a Alegra ────────────────────────────────────────
        result = self._run_phase(7, "Carga a Alegra", self._fase7_cargar)
        if result["status"] == PHASE_STATUS_FAILED:
            logger.warning("Carga masiva fallida. Intentando fallback individual...")
            result = self._run_phase(
                7, "Carga Individual (Fallback)",
                self.upload_agent.fallback_individual_upload,
                self._template_df,
            )

        return self.generate_final_report()

    # ─── Wrapper de fases ─────────────────────────────────────────────────

    def _run_phase(
        self,
        phase_number: int,
        phase_name: str,
        func: Callable,
        *args: Any,
    ) -> dict:
        key = f"phase_{phase_number}"
        logger.info(f"\n{'─'*50}")
        logger.info(f"FASE {phase_number}: {phase_name.upper()}")

        t0 = time.time()
        try:
            data = func(*args)
            elapsed = round(time.time() - t0, 2)

            # Determinar status según datos
            status = self._infer_status(phase_number, data)
            result = {
                "phase": phase_number,
                "name": phase_name,
                "status": status,
                "data": data,
                "elapsed_s": elapsed,
                "error": None,
            }
            icon = "✅" if status == PHASE_STATUS_OK else ("⚠️" if status == PHASE_STATUS_WARN else "❌")
            logger.info(f"{icon} Fase {phase_number} completada en {elapsed}s — status: {status}")

        except (AlegraConnectionError, ValidationError, TemplateError) as exc:
            elapsed = round(time.time() - t0, 2)
            logger.error(f"❌ Fase {phase_number} FALLIDA ({elapsed}s): {exc}")
            result = {
                "phase": phase_number,
                "name": phase_name,
                "status": PHASE_STATUS_FAILED,
                "data": None,
                "elapsed_s": elapsed,
                "error": str(exc),
            }
        except Exception as exc:
            elapsed = round(time.time() - t0, 2)
            logger.exception(f"❌ Fase {phase_number} ERROR INESPERADO ({elapsed}s): {exc}")
            result = {
                "phase": phase_number,
                "name": phase_name,
                "status": PHASE_STATUS_FAILED,
                "data": None,
                "elapsed_s": elapsed,
                "error": str(exc),
            }

        self.phase_results[key] = result
        return result

    def _infer_status(self, phase_number: int, data: Any) -> str:
        """Infiere el status de una fase según los datos retornados."""
        if data is None:
            return PHASE_STATUS_OK

        if isinstance(data, dict):
            # Fase 3: terceros
            if phase_number == 3:
                if data.get("failed"):
                    return PHASE_STATUS_WARN
                return PHASE_STATUS_OK
            # Fase 4: plan de cuentas
            if phase_number == 4:
                if not data.get("valid", True):
                    return PHASE_STATUS_FAILED
                return PHASE_STATUS_OK
            # Fase 5: plantilla
            if phase_number == 5:
                if not data.get("valid", True):
                    return PHASE_STATUS_FAILED
                return PHASE_STATUS_OK
            # Fase 6: gate
            if phase_number == 6:
                if not data.get("passed", True):
                    return PHASE_STATUS_BLOCKED
                return PHASE_STATUS_OK
            # Gate general: "valid" key
            if "valid" in data and not data["valid"]:
                return PHASE_STATUS_FAILED
            if "success" in data and not data["success"]:
                return PHASE_STATUS_FAILED

        return PHASE_STATUS_OK

    # ─── Lógica de fases específicas ──────────────────────────────────────

    def _fase2_leer_transacciones(self) -> dict:
        df = self.template_agent.read_transaction_files(str(TRANSACTIONS_FOLDER))
        col_check = self.template_agent.validate_required_columns(df)
        if not col_check["valid"]:
            raise ValidationError(
                f"Columnas faltantes: {col_check['missing_columns']}",
                details=col_check,
            )
        self._transactions_df = df
        return {"valid": True, "rows": len(df), "columns": list(df.columns)}

    def _fase4_verificar_cuentas(self) -> dict:
        accounts = self.coa_agent.get_full_chart_of_accounts()
        self._accounts_lookup = self.coa_agent.build_accounts_lookup(accounts)
        verification = self.coa_agent.verify_accounts_in_transactions(
            self._transactions_df, self._accounts_lookup
        )
        if not verification["valid"]:
            missing = verification.get("accounts_missing", [])
            inactive = verification.get("accounts_inactive", [])
            issues = []
            if missing:
                issues.append(f"Cuentas inexistentes: {missing}")
            if inactive:
                issues.append(f"Cuentas inactivas: {inactive}")
            raise ValidationError(
                "Plan de cuentas inválido. " + " | ".join(issues),
                details=verification,
            )
        return verification

    def _fase5_generar_plantilla(self) -> dict:
        template_df = self.template_agent.transform_to_alegra_format(
            self._transactions_df, self._contacts_map, self._accounts_lookup
        )
        completeness = self.template_agent.validate_template_completeness(template_df)
        if not completeness["valid"]:
            raise TemplateError(
                f"Plantilla incompleta: {len(completeness['rows_with_errors'])} filas con errores.",
                row_errors=completeness["rows_with_errors"],
            )
        self._template_path = self.template_agent.export_template(
            template_df, str(TEMPLATES_OUTPUT_FOLDER)
        )
        self._template_df = template_df
        return {
            "valid": True,
            "total_rows": completeness["total_rows"],
            "template_path": self._template_path,
        }

    def _fase7_cargar(self) -> dict:
        response = self.upload_agent.upload_template(self._template_path)
        result = self.upload_agent.verify_upload_result(response)
        if not result["success"]:
            raise AlegraConnectionError(
                f"Importación masiva fallida: {result['failed']} errores"
            )
        return result

    # ─── Gate pre-carga ───────────────────────────────────────────────────

    def _validate_pre_upload_checklist(self) -> dict:
        """Fase 6: verifica el checklist completo antes de la carga."""
        checklist: dict[str, bool] = {}
        blocking: list[str] = []

        # 1. Conexión API activa
        checklist["conexion_api_activa"] = (
            self.phase_results.get("phase_1", {}).get("status") == PHASE_STATUS_OK
        )

        # 2. Terceros: todos requeridos existen (o solo hay warns)
        contacts_data = self.phase_results.get("phase_3", {}).get("data", {}) or {}
        failed_contacts = contacts_data.get("failed", [])
        checklist["terceros_ok"] = len(failed_contacts) == 0

        # 3. Cuentas verificadas
        coa_data = self.phase_results.get("phase_4", {}).get("data", {}) or {}
        checklist["cuentas_verificadas"] = coa_data.get("valid", False)

        # 4. Plantilla generada sin errores
        tpl_data = self.phase_results.get("phase_5", {}).get("data", {}) or {}
        checklist["plantilla_sin_errores"] = tpl_data.get("valid", False)

        # 5. Archivo CSV existe y es legible
        checklist["archivo_csv_legible"] = (
            bool(self._template_path) and Path(self._template_path).exists()
        )

        # 6. Comprobantes balanceados (si la fase 5 pasó, el balance fue verificado)
        checklist["comprobantes_balanceados"] = tpl_data.get("valid", False)

        # Determinar bloqueos
        for key, passed in checklist.items():
            if not passed:
                blocking.append(key)

        result = {
            "passed": len(blocking) == 0,
            "checklist": checklist,
            "blocking_issues": blocking,
        }

        if result["passed"]:
            logger.success("Gate pre-carga: ✅ Todos los checks aprobados.")
        else:
            logger.error(f"Gate pre-carga: ❌ Checks fallidos — {blocking}")

        return result

    # ─── Reporte final ────────────────────────────────────────────────────

    def generate_final_report(self) -> dict:
        elapsed = round(time.time() - self.start_time, 2)
        lines: list[str] = []

        lines.append("\n" + "=" * 60)
        lines.append("   REPORTE FINAL — CARGA DE COMPROBANTES ALEGRA")
        lines.append(f"   Ejecutado: {self._run_ts}")
        lines.append("=" * 60)

        status_icons = {
            PHASE_STATUS_OK: "✅",
            PHASE_STATUS_WARN: "⚠️",
            PHASE_STATUS_FAILED: "❌",
            PHASE_STATUS_BLOCKED: "🔒",
            PHASE_STATUS_SKIPPED: "⏭️",
        }

        for key in sorted(self.phase_results):
            p = self.phase_results[key]
            icon = status_icons.get(p["status"], "?")
            lines.append(
                f"  {icon} Fase {p['phase']:1d}: {p['name']:<35s} "
                f"[{p['status']:<8s}] {p['elapsed_s']}s"
            )
            if p.get("error"):
                lines.append(f"       Error: {p['error']}")

        lines.append("")
        lines.append("── Estadísticas ──────────────────────────────────────")

        # Terceros
        contacts_data = self.phase_results.get("phase_3", {}).get("data") or {}
        lines.append(
            f"  Terceros — requeridos: {contacts_data.get('total_required', 'n/a')}, "
            f"creados: {contacts_data.get('created', 'n/a')}, "
            f"fallidos: {len(contacts_data.get('failed', []))}"
        )

        # Cuentas
        coa_data = self.phase_results.get("phase_4", {}).get("data") or {}
        lines.append(
            f"  Cuentas — verificadas: {len(coa_data.get('accounts_found', []))}, "
            f"faltantes: {len(coa_data.get('accounts_missing', []))}, "
            f"inactivas: {len(coa_data.get('accounts_inactive', []))}"
        )

        # Plantilla
        tpl_data = self.phase_results.get("phase_5", {}).get("data") or {}
        lines.append(f"  Filas en plantilla: {tpl_data.get('total_rows', 'n/a')}")
        if self._template_path:
            lines.append(f"  Archivo generado: {self._template_path}")

        # Comprobantes creados
        upload_data = self.phase_results.get("phase_7", {}).get("data") or {}
        if isinstance(upload_data, dict):
            ids = upload_data.get("journal_entry_ids", [])
            if ids:
                lines.append(f"  IDs Comprobantes creados ({len(ids)}): {ids[:10]}")
                if len(ids) > 10:
                    lines.append(f"    ... y {len(ids) - 10} más")
            lines.append(
                f"  Carga — exitosos: {upload_data.get('successful', 'n/a')}, "
                f"fallidos: {upload_data.get('failed', 'n/a')}"
            )

        lines.append("")
        lines.append(f"  Tiempo total: {elapsed}s")
        lines.append("=" * 60)

        report_text = "\n".join(lines)
        for line in lines:
            logger.info(line)

        # Guardar en archivo
        try:
            LOGS_FOLDER.mkdir(parents=True, exist_ok=True)
            log_file = LOGS_FOLDER / f"report_{self._run_ts}.txt"
            log_file.write_text(report_text, encoding="utf-8")
            logger.info(f"Reporte guardado en: {log_file}")
        except Exception as exc:
            logger.warning(f"No se pudo guardar el reporte: {exc}")

        overall_ok = all(
            p["status"] in (PHASE_STATUS_OK, PHASE_STATUS_WARN)
            for p in self.phase_results.values()
        )
        return {"success": overall_ok, "report": report_text, "phases": self.phase_results}

    def _abort(self, reason: str) -> dict:
        logger.error(f"PROCESO ABORTADO: {reason}")
        return self.generate_final_report()
