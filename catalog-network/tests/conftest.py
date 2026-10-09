import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from fastapi.testclient import TestClient  # noqa: E402

from nexus_catalog.app import create_app  # noqa: E402
from nexus_catalog.config import Settings  # noqa: E402
from nexus_catalog.db import Catalog  # noqa: E402

TOKEN = "test-token-0123456789abcdef"
FIXTURES = HERE / "fixtures"


@pytest.fixture
def collection() -> bytes:
    return (FIXTURES / "collection.xml").read_bytes()


@pytest.fixture
def catalog(tmp_path):
    cat = Catalog(tmp_path / "catalog.db")
    yield cat
    cat.close()


@pytest.fixture
def client(catalog, tmp_path):
    settings = Settings(db_path=tmp_path / "catalog.db", tokens=f"biblioteca-a:{TOKEN}")
    with TestClient(create_app(settings, catalog)) as c:
        yield c


@pytest.fixture
def loaded(client, collection):
    r = client.post("/api/records/sync", content=collection, headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/marcxml+xml"})
    assert r.status_code == 200, r.text
    return client
