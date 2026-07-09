"""Shared pytest fixtures for the backend test suite.

No respx/HTTP-mocking dependency is added — httpx.AsyncClient calls are
stubbed directly via unittest.mock, per 02-RESEARCH.md's Wave 0 test map.
"""

import pytest


@pytest.fixture
def mock_ado_env(monkeypatch):
    """Set the minimal ADO env vars every ado_client call reads fresh from os.environ."""
    monkeypatch.setenv("ADO_ORG", "testorg")
    monkeypatch.setenv("ADO_PROJECT", "testproj")
    monkeypatch.setenv("ADO_PAT", "testpat")
