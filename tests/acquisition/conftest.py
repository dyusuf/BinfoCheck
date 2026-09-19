from collections.abc import Iterator
from pathlib import Path

import pytest

from binfocheck.storage import MemoryStore, SQLiteStore

from .helpers import Store


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("Acquisition tests must not open network connections")

    monkeypatch.setattr("socket.create_connection", blocked)
    monkeypatch.setattr("socket.socket.connect", blocked)


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Store]:
    backend = MemoryStore() if request.param == "memory" else SQLiteStore(tmp_path / "store")
    yield backend
    backend.close()
