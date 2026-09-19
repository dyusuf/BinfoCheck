from collections.abc import Iterator
from pathlib import Path

import pytest

from binfocheck.storage import MemoryStore, SQLiteStore

from .helpers import Store


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Store]:
    backend = MemoryStore() if request.param == "memory" else SQLiteStore(tmp_path / "store")
    yield backend
    backend.close()
