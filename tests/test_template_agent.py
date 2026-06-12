"""Tests del TemplateAgent."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from agents.template_agent import TemplateAgent
from utils.validators import TemplateError, ValidationError

SAMPLE_COLS = [
    "fecha", "descripcion", "nit_tercero", "nombre_tercero", "tipo_tercero",
    "codigo_cuenta", "nombre_cuenta", "debito", "credito", "numero_comprobante",
]


def make_sample_df(rows: list[dict] | None = None) -> pd.DataFrame:
    default = [
        {
            "fecha": "2024-01-15",
            "descripcion": "Compra de mercancía",
            "nit_tercero": "900123456",
            "nombre_tercero": "Proveedor A",
            "tipo_tercero": "proveedor",
            "codigo_cuenta": "1305",
            "nombre_cuenta": "Mercancías",
            "debito": "500000",
            "credito": "0",
            "numero_comprobante": "CP001",
        },
        {
            "fecha": "2024-01-15",
            "descripcion": "Compra de mercancía",
            "nit_tercero": "900123456",
            "nombre_tercero": "Proveedor A",
            "tipo_tercero": "proveedor",
            "codigo_cuenta": "2205",
            "nombre_cuenta": "Proveedores",
            "debito": "0",
            "credito": "500000",
            "numero_comprobante": "CP001",
        },
    ]
    return pd.DataFrame(rows or default)


@pytest.fixture
def agent():
    return TemplateAgent()


def test_validate_required_columns_ok(agent):
    df = make_sample_df()
    result = agent.validate_required_columns(df)
    assert result["valid"] is True
    assert result["missing_columns"] == []


def test_validate_required_columns_missing(agent):
    df = pd.DataFrame({"fecha": ["2024-01-01"], "descripcion": ["test"]})
    result = agent.validate_required_columns(df)
    assert result["valid"] is False
    assert len(result["missing_columns"]) > 0


def test_transform_to_alegra_format_ok(agent):
    df = make_sample_df()
    contacts_map = {"900123456": 10}
    accounts_lookup = {
        "1305": {"id": 100, "code": "1305"},
        "2205": {"id": 200, "code": "2205"},
    }
    result = agent.transform_to_alegra_format(df, contacts_map, accounts_lookup)

    assert len(result) == 2
    assert result.iloc[0]["date"] == "2024-01-15"
    assert result.iloc[0]["account"] == 100
    assert result.iloc[0]["contact"] == 10


def test_transform_balance_error(agent):
    rows = make_sample_df().to_dict("records")
    rows[1]["credito"] = "999999"  # romper balance
    df = pd.DataFrame(rows)
    contacts_map = {"900123456": 10}
    accounts_lookup = {
        "1305": {"id": 100},
        "2205": {"id": 200},
    }
    with pytest.raises(TemplateError):
        agent.transform_to_alegra_format(df, contacts_map, accounts_lookup)


def test_validate_template_completeness_ok(agent):
    df = pd.DataFrame({
        "date": ["2024-01-15"],
        "description": ["Compra"],
        "account": [100],
        "debit": [500000.0],
        "credit": [0.0],
        "contact": [10],
        "costCenter": [""],
        "observations": [""],
        "_numero_comprobante": ["CP001"],
        "_source_row": [0],
    })
    result = agent.validate_template_completeness(df)
    assert result["valid"] is True


def test_validate_template_completeness_empty_required(agent):
    df = pd.DataFrame({
        "date": [""],
        "description": ["Compra"],
        "account": [100],
        "debit": [0.0],
        "credit": [0.0],
        "contact": [10],
        "costCenter": [""],
        "observations": [""],
        "_numero_comprobante": ["CP001"],
        "_source_row": [0],
    })
    result = agent.validate_template_completeness(df)
    assert result["valid"] is False
    assert len(result["rows_with_errors"]) > 0


def test_export_template(agent):
    df = pd.DataFrame({
        "date": ["2024-01-15"],
        "description": ["Compra"],
        "account": [100],
        "debit": [500000.0],
        "credit": [0.0],
        "contact": [10],
        "costCenter": [""],
        "observations": [""],
    })
    with tempfile.TemporaryDirectory() as tmp:
        path = agent.export_template(df, tmp)
        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8-sig")
        assert "date" in content
        assert "2024-01-15" in content


def test_read_transaction_files_no_files(agent):
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValidationError):
            agent.read_transaction_files(tmp)


def test_read_transaction_files_csv(agent):
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "transactions.csv"
        df_sample = make_sample_df()
        df_sample.to_csv(csv_path, index=False, encoding="utf-8-sig")

        result = agent.read_transaction_files(tmp)
        assert len(result) == 2
