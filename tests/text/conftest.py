from collections.abc import Iterator
from pathlib import Path

import pytest

from binfocheck.storage import MemoryStore, SQLiteStore
from tests.storage.helpers import Store


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("T02 tests must not use network")

    monkeypatch.setattr("socket.create_connection", blocked)
    monkeypatch.setattr("socket.socket.connect", blocked)
    monkeypatch.setattr("socket.socket.connect_ex", blocked)


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Store]:
    backend = MemoryStore() if request.param == "memory" else SQLiteStore(tmp_path / "store")
    yield backend
    backend.close()
