from pathlib import Path

import pytest

from binfocheck.storage import SQLiteStore
from binfocheck.text.errors import TextError
from binfocheck.text.verify_saved_capture import fingerprint, verify

from .helpers import seed


def test_complete_copy_before_any_sqlite_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = tmp_path / "source"
    with SQLiteStore(original) as store:
        request, _ = seed(store, "# Heading\n\nOne. Two.\n\n- Three.")
    before = fingerprint(original)
    opened: list[Path] = []

    def copied_only(path: Path) -> SQLiteStore:
        assert path != original
        assert (path / "store.sqlite3").is_file()
        if not opened:
            assert fingerprint(path) == before
        opened.append(path)
        return SQLiteStore(path)

    monkeypatch.setattr("binfocheck.text.verify_saved_capture.SQLiteStore", copied_only)
    result = verify(original, request.observation_id)
    assert result["status"] == "passed" and result["provider_calls"] == 0
    assert result["source_unchanged"] is True
    assert fingerprint(original) == before
    assert len(opened) == 2 and opened[0] == opened[1]


def test_missing_capture_does_not_recapture(tmp_path: Path) -> None:
    with pytest.raises(TextError) as error:
        verify(tmp_path / "absent", "obs")
    assert error.value.detail.code == "saved_capture_missing"
