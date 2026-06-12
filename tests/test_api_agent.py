"""Tests del APIAgent."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.api_agent import APIAgent
from utils.validators import AlegraConnectionError


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_session.return_value = MagicMock(auth=("user@test.com", "token"))
    return client


def test_verify_connection_ok(mock_client):
    mock_client.get.return_value = [{"id": 1, "name": "Test Contact"}]
    agent = APIAgent(mock_client)
    result = agent.verify_connection()

    assert result["success"] is True
    assert result["status_code"] == 200
    mock_client.get.assert_called_once_with("/contacts", params={"limit": 1})


def test_verify_connection_api_error(mock_client):
    from utils.validators import AlegraAPIError
    mock_client.get.side_effect = AlegraAPIError("Unauthorized", status_code=401)
    agent = APIAgent(mock_client)

    with pytest.raises(AlegraConnectionError):
        agent.verify_connection()


def test_verify_connection_network_error(mock_client):
    mock_client.get.side_effect = AlegraConnectionError("Sin conexión")
    agent = APIAgent(mock_client)

    with pytest.raises(AlegraConnectionError):
        agent.verify_connection()


def test_get_authenticated_session(mock_client):
    agent = APIAgent(mock_client)
    session = agent.get_authenticated_session()
    assert session is not None
    mock_client.get_session.assert_called_once()


def test_test_rate_limit_available(mock_client):
    mock_client.get.return_value = []
    agent = APIAgent(mock_client)
    assert agent.test_rate_limit() is True


def test_test_rate_limit_throttled(mock_client):
    from utils.validators import AlegraRateLimitError
    mock_client.get.side_effect = AlegraRateLimitError("429", status_code=429)
    agent = APIAgent(mock_client)
    assert agent.test_rate_limit() is False
