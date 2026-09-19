import json
from pathlib import Path

import pytest

from binfocheck.corpus.__main__ import main
from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.config import POLICY, ROBOTS, URLS, capture_policy_sha256
from binfocheck.corpus.errors import require
from binfocheck.corpus.ingestion import StoredCorpusIngestor
from binfocheck.storage import SQLiteStore

from .helpers import capture, request


def test_policy_is_explicitly_unapproved(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["proposed-policy"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["authorized"] is False
    assert output["robots_url"] == ROBOTS
    assert output["authorization_policy_sha256"] == capture_policy_sha256(ROBOTS, URLS, POLICY)
    assert output["urls"] == list(URLS)
    assert output["policy"] == POLICY.model_dump(mode="json")


def test_cli_replays_and_inspects_saved_store(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "store"
    with SQLiteStore(root) as backend:
        batch = capture(Store(backend, backend))
        result = require(StoredCorpusIngestor(backend, backend).ingest(request(batch)))
    input_path = tmp_path / "request.json"
    input_path.write_text(request(batch).model_dump_json())
    assert main(["replay", "--store", str(root), "--request", str(input_path)]) == 0
    assert json.loads(capsys.readouterr().out)["manifest_id"] == result.manifest.id
    assert main(["inspect", "--store", str(root), "--manifest", result.manifest.id]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ready"


def test_no_capture_cli() -> None:
    with pytest.raises(SystemExit):
        main(["capture"])
