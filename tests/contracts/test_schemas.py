import json
from pathlib import Path

from jsonschema import Draft202012Validator

from binfocheck.domain.export_schemas import DEFAULT_OUTPUT, check_schemas, render_schemas


def test_committed_exports_match_models() -> None:
    assert check_schemas(DEFAULT_OUTPUT) == []
    for content in render_schemas().values():
        Draft202012Validator.check_schema(json.loads(content))


def test_drift_check_detects_changed_missing_and_extra_files(tmp_path: Path) -> None:
    exports = render_schemas()
    for name, content in exports.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    assert check_schemas(tmp_path) == []
    names = sorted(exports)
    (tmp_path / names[0]).write_text("{}\n", encoding="utf-8")
    (tmp_path / names[1]).unlink()
    (tmp_path / "unexpected.json").write_text("{}\n", encoding="utf-8")
    assert set(check_schemas(tmp_path)) == {
        f"changed: {names[0]}",
        f"missing: {names[1]}",
        "unexpected: unexpected.json",
    }
