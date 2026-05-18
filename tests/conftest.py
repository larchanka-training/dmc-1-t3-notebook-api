from typing import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """
    Generates a synchronized TestClient for integration execution loops.
    """
    with TestClient(app) as test_client:
        yield test_client
