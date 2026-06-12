"""Tests del ContactsAgent."""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from agents.contacts_agent import ContactsAgent
from utils.validators import ValidationError


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "fecha": ["2024-01-15", "2024-01-15"],
        "descripcion": ["Compra", "Compra"],
        "nit_tercero": ["900123456", "800987654"],
        "nombre_tercero": ["Proveedor A", "Proveedor B"],
        "tipo_tercero": ["proveedor", "proveedor"],
        "codigo_cuenta": ["1305", "2205"],
        "nombre_cuenta": ["Mercancías", "Proveedores"],
        "debito": [500000, 0],
        "credito": [0, 500000],
        "numero_comprobante": ["CP001", "CP001"],
    })


def test_extract_contacts_from_transactions(mock_client, sample_df):
    agent = ContactsAgent(mock_client)
    contacts = agent.extract_contacts_from_transactions(sample_df)

    assert len(contacts) == 2
    nits = [c["identification"] for c in contacts]
    assert "900123456" in nits
    assert "800987654" in nits


def test_extract_contacts_missing_columns(mock_client):
    agent = ContactsAgent(mock_client)
    bad_df = pd.DataFrame({"fecha": ["2024-01-01"]})
    with pytest.raises(ValidationError):
        agent.extract_contacts_from_transactions(bad_df)


def test_find_missing_contacts(mock_client):
    agent = ContactsAgent(mock_client)
    required = [
        {"identification": "900123456", "name": "Proveedor A", "type": "provider"},
        {"identification": "111111111", "name": "Nuevo", "type": "other"},
    ]
    existing = [
        {"id": 1, "identification": "900123456", "name": "Proveedor A"},
    ]
    missing = agent.find_missing_contacts(required, existing)
    assert len(missing) == 1
    assert missing[0]["identification"] == "111111111"


def test_find_missing_contacts_none_missing(mock_client):
    agent = ContactsAgent(mock_client)
    required = [{"identification": "900123456", "name": "A", "type": "provider"}]
    existing = [{"id": 1, "identification": "900123456"}]
    missing = agent.find_missing_contacts(required, existing)
    assert len(missing) == 0


def test_create_contact(mock_client):
    mock_client.post.return_value = {"id": 42, "name": "Proveedor A", "identification": "900123456"}
    agent = ContactsAgent(mock_client)
    contact = {"identification": "900123456", "name": "Proveedor A", "type": "provider"}
    result = agent.create_contact(contact)

    assert result["id"] == 42
    mock_client.post.assert_called_once_with(
        "/contacts",
        {"name": "Proveedor A", "identification": "900123456", "type": ["provider"]},
    )


def test_ensure_all_contacts_exist_creates_missing(mock_client, sample_df):
    mock_client.get_paginated.return_value = [
        {"id": 1, "identification": "900123456", "name": "Proveedor A"},
    ]
    mock_client.post.return_value = {"id": 2, "identification": "800987654", "name": "Proveedor B"}

    agent = ContactsAgent(mock_client)
    result = agent.ensure_all_contacts_exist(sample_df)

    assert result["total_required"] == 2
    assert result["already_existed"] == 1
    assert result["created"] == 1
    assert len(result["failed"]) == 0
    assert "800987654" in result["contacts_map"]
