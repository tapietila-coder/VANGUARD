import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from vanguard.api.app import create_app
from vanguard.core.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        db_path=str(tmp_path / "vanguard.db"),
        api_token="test-token-0123456789abcdef0123",
        environment="dev",
        dispatch_base_url="http://127.0.0.1:8787",
        mesh_provider="null",
        node_stale_after_seconds=300,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def auth_headers(settings):
    return {"Authorization": f"Bearer {settings.api_token}"}
