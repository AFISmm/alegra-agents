from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from config import REQUIRED_TRANSACTION_COLUMNS, OPTIONAL_TRANSACTION_COLUMNS, ALEGRA_TEMPLATE_COLUMNS
from utils.validators import ValidationError, TemplateError, validate_amount, validate_date
from utils.siigo_parser import is_siigo_auxiliary, parse_siigo_auxiliary


class TemplateAgent:
    """Agente 4: Procesa archivos de transacciones y genera la plantilla CSV de Alegra."""

    # ─── Lectura de archivos ────────────────────────────────────────────────

    def read_transaction_files(self, folder_path: str) -> pd.DataFrame:
        """Lee todos los archivos xlsx/csv/xls de la carpeta y los consolida.

        Detecta automáticamente el formato Siigo Auxiliar y lo parsea correctamente.
        """
        folder = Path(folder_path)
        if not folder.exists():
            raise ValidationError(f"Carpeta de transacciones no existe: {folder}")

        files = list(folder.glob("*.xlsx")) + list(folder.glob("*.xls")) + list(folder.glob("*.csv"))
        files = [f for f in files if not f.name.startswith("~$")]

        if not files:
            raise ValidationError(f"No se encontraron archivos en {folder}")

        frames: list[pd.DataFrame] = []
        for file in files:
            try:
                if file.suffix.lower() in (".xlsx", ".xls") and is_siigo_auxiliary(file):
                    logger.info(f"TemplateAgent: '{file.name}' detectado como Libro Auxiliar Siigo.")
                    df = parse_siigo_auxiliary(file)
                else:
                    df = self._read_single_file(file)
                    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
                df = df.assign(_source_file=file.name)
                frames.append(df)
                logger.info(f"TemplateAgent: {file.name} -> {len(df)} filas leidas.")
            except Exception as exc:
                logger.error(f"TemplateAgent: error leyendo {file.name} — {exc}")
                raise

        combined = pd.concat(frames, ignore_index=True)
        logger.info(f"TemplateAgent: total consolidado -> {len(combined)} filas de {len(files)} archivos.")
        return combined

    def _read_single_file(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            return pd.read_excel(path, dtype=str)
        elif suffix == ".csv":
            for enc in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    return pd.read_csv(path, dtype=str, encoding=enc, sep=None, engine="python")
                except UnicodeDecodeError:
                    continue
            raise ValidationError(f"No se pudo decodificar el archivo CSV: {path.name}")
        else:
            raise ValidationError(f"Formato no soportado: {suffix}")

    # ─── Validación de columnas ────────────────────────────────────────────

    def validate_required_columns(self, df: pd.DataFrame) -> dict:
        """Verifica columnas requeridas; retorna resumen."""
        existing = set(df.columns)
        required = set(REQUIRED_TRANSACTION_COLUMNS)
        optional = set(OPTIONAL_TRANSACTION_COLUMNS)

        missing = sorted(required - existing)
        extra = sorted(existing - required - optional - {"_source_file"})
        valid = len(missing) == 0

        if not valid:
            logger.error(f"TemplateAgent: columnas faltantes — {missing}")
        else:
            logger.success("TemplateAgent: todas las columnas requeridas presentes.")

        return {"valid": valid, "missing_columns": missing, "extra_columns": extra}

    # ─── Transformación ────────────────────────────────────────────────────

    def transform_to_alegra_format(
        self,
        df: pd.DataFrame,
        contacts_map: dict[str, int],
        accounts_lookup: dict[str, dict],
    ) -> pd.DataFrame:
        """Transforma el DataFrame al formato columnar de Alegra y verifica balances."""
        rows_ok: list[dict] = []
        rows_error: list[dict] = []

        for idx, row in df.iterrows():
            try:
                fecha = validate_date(row["fecha"])
                debito = validate_amount(row.get("debito", 0) or 0)
                credito = validate_amount(row.get("credito", 0) or 0)

                nit = str(row.get("nit_tercero", "")).strip().replace(".", "").replace("-", "")
                contact_id = contacts_map.get(nit, nit)

                code = str(row.get("codigo_cuenta", "")).strip()
                account_data = accounts_lookup.get(code, {})
                account_id = account_data.get("id", code)

                rows_ok.append({
                    "date": fecha,
                    "description": str(row.get("descripcion", "")).strip(),
                    "account": account_id,
                    "debit": debito,
                    "credit": credito,
                    "contact": contact_id,
                    "costCenter": str(row.get("centro_costo", "") or "").strip(),
                    "observations": str(row.get("observaciones", "") or "").strip(),
                    "_numero_comprobante": str(row.get("numero_comprobante", "")).strip(),
                    "_source_row": idx,
                })
            except Exception as exc:
                logger.warning(f"TemplateAgent: error en fila {idx} — {exc}")
                rows_error.append({"row": idx, "error": str(exc)})

        if rows_error:
            logger.warning(f"TemplateAgent: {len(rows_error)} filas con errores de transformación.")

        result_df = pd.DataFrame(rows_ok)

        # Verificar balance por comprobante
        if not result_df.empty:
            balance_errors = self._check_balance(result_df)
            if balance_errors:
                for be in balance_errors:
                    logger.error(
                        f"TemplateAgent: comprobante '{be['numero_comprobante']}' NO balancea — "
                        f"débito={be['total_debit']:.2f}, crédito={be['total_credit']:.2f}"
                    )
                raise TemplateError(
                    f"{len(balance_errors)} comprobante(s) no balancean",
                    row_errors=balance_errors,
                )

        logger.success(f"TemplateAgent: {len(result_df)} filas transformadas correctamente.")
        return result_df

    def _check_balance(self, df: pd.DataFrame) -> list[dict]:
        """Verifica que débito == crédito por número de comprobante."""
        errors: list[dict] = []
        for num, group in df.groupby("_numero_comprobante"):
            total_d = round(group["debit"].sum(), 2)
            total_c = round(group["credit"].sum(), 2)
            if abs(total_d - total_c) > 0.01:
                errors.append({
                    "numero_comprobante": num,
                    "total_debit": total_d,
                    "total_credit": total_c,
                    "diff": abs(total_d - total_c),
                })
        return errors

    # ─── Validación final ──────────────────────────────────────────────────

    def validate_template_completeness(self, df: pd.DataFrame) -> dict:
        """Verifica que no haya campos requeridos vacíos en la plantilla final."""
        mandatory = ["date", "description", "account"]
        rows_with_errors: list[int] = []
        error_detail: dict[int, list[str]] = {}

        for idx, row in df.iterrows():
            issues: list[str] = []
            for col in mandatory:
                if not str(row.get(col, "")).strip():
                    issues.append(col)
            if row.get("debit", 0) == 0 and row.get("credit", 0) == 0:
                issues.append("debit_y_credit_ambos_cero")
            if issues:
                rows_with_errors.append(idx)
                error_detail[idx] = issues

        valid = len(rows_with_errors) == 0
        if not valid:
            logger.error(f"TemplateAgent: {len(rows_with_errors)} filas con campos vacíos obligatorios.")
        else:
            logger.success("TemplateAgent: plantilla completa y sin campos vacíos requeridos.")

        return {
            "valid": valid,
            "total_rows": len(df),
            "rows_with_errors": rows_with_errors,
            "error_detail": error_detail,
        }

    # ─── Exportación ──────────────────────────────────────────────────────

    def export_template(self, df: pd.DataFrame, output_path: str) -> str:
        """Exporta la plantilla como CSV UTF-8 con BOM. Retorna la ruta del archivo."""
        folder = Path(output_path)
        folder.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = folder / f"comprobantes_{timestamp}.csv"

        export_cols = [c for c in ALEGRA_TEMPLATE_COLUMNS if c in df.columns]
        df[export_cols].to_csv(filename, index=False, encoding="utf-8-sig")

        logger.success(f"TemplateAgent: plantilla exportada -> {filename}")
        return str(filename)
