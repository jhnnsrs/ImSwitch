"""
Shared pytest fixtures for API tests.
"""

import pytest
from fastapi.testclient import TestClient

from refactor.api import create_app


@pytest.fixture
def client():
    """Create a test client with lifespan context."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def app():
    """Create a test app instance."""
    return create_app()
