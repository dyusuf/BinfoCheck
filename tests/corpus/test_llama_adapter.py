import os
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

import pytest
from llama_index.core import Settings
from llama_index.core.ingestion import IngestionPipeline

from binfocheck.corpus import StoredCorpusIngestor
from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.errors import require
from binfocheck.storage import MemoryStore

from .helpers import capture, request


def test_no_implicit_defaults_models_network_or_indexes(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError("implicit model/default initialization forbidden")

    monkeypatch.setattr(IngestionPipeline, "_get_default_transformations", forbidden)
    import llama_index.core.settings as settings_module

    monkeypatch.setattr(settings_module, "resolve_llm", forbidden)
    monkeypatch.setattr(settings_module, "resolve_embed_model", forbidden)
    before = (vars(Settings)["_llm"], vars(Settings)["_embed_model"])
    with MemoryStore() as backend:
        result = require(
            StoredCorpusIngestor(backend, backend).ingest(request(capture(Store(backend, backend))))
        )
        assert result.manifest.status == "ready"
    assert (vars(Settings)["_llm"], vars(Settings)["_embed_model"]) == before


def test_cold_import_and_ingestion_with_network_and_downloads_blocked(tmp_path: Path) -> None:
    # Collection imports precede pytest's autouse socket guard. Cover a fresh process too.
    script = """
import os
import socket
from pathlib import Path

def forbidden(*args, **kwargs):
    raise AssertionError("network or model-resource download attempted")
socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden
socket.create_connection = forbidden
socket.getaddrinfo = forbidden
import nltk
nltk.download = forbidden
from binfocheck.corpus import StoredCorpusIngestor
from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.errors import require
from binfocheck.storage import MemoryStore
from tests.corpus.helpers import capture, request
with MemoryStore() as store:
    batch = capture(Store(store, store))
    result = require(StoredCorpusIngestor(store, store).ingest(request(batch)))
    assert result.manifest.status == "ready"
assert not Path(os.environ["NLTK_DATA"]).exists()
"""
    environment = dict(os.environ, NLTK_DATA=str(tmp_path / "unused-nltk"))
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
