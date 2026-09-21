"""Regression coverage for generated README task progress."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/update-readme-status.py"
TASKS = [
    ("T00", "Contracts, scaffold and CI", "accepted"),
    ("T11A", "Shared storage", "accepted"),
    ("T01", "Google AI Mode acquisition", "accepted"),
    ("T02", "Answer indexing/context", "accepted"),
    ("T03", "Model adapters", "integration_blocked"),
    ("T04", "Claim extraction", "integration_blocked"),
    ("T05", "Citation mapping", "integration_blocked"),
    ("T06", "diabinfo.de corpus", "accepted"),
    ("T07", "Hybrid retrieval", "accepted"),
    ("T08", "Candidate verification", "not_started"),
    ("T09", "Alternative-source analysis", "not_started"),
    ("T10", "Evidence classification", "not_started"),
    ("T11B", "Pipeline execution", "not_started"),
    ("T12", "API", "not_started"),
    ("T13", "Editorial dashboard", "not_started"),
    ("T14", "End-to-end/deployment", "not_started"),
]


def seed(root: Path, *, status_override: str | None = None) -> None:
    (root / "docs").mkdir()
    tasks = [
        {"id": task_id, "component": component, "status": status_override or status}
        for task_id, component, status in TASKS
    ]
    (root / "docs/task-status.json").write_text(
        json.dumps({"version": 1, "tasks": tasks}), encoding="utf-8"
    )
    anchors = "\n".join(f'<a id="{task_id.lower()}"></a>' for task_id, _, _ in TASKS)
    (root / "docs/implementation-plan.md").write_text(anchors + "\n", encoding="utf-8")
    (root / "README.md").write_text(
        "# Test\n\n<!-- TASK-STATUS:START -->\nstale\n<!-- TASK-STATUS:END -->\n",
        encoding="utf-8",
    )


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_generator_updates_and_check_detects_drift(tmp_path: Path) -> None:
    seed(tmp_path)
    updated = run(tmp_path)
    assert updated.returncode == 0, updated.stdout + updated.stderr

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert (
        "| T04 | [Claim extraction](docs/implementation-plan.md#t04) | "
        "🟡 Integration blocked |"
    ) in readme
    assert (
        "| T07 | [Hybrid retrieval](docs/implementation-plan.md#t07) | ✅ Accepted |"
        in readme
    )
    assert "Detailed acceptance criteria and evidence" not in readme
    assert run(tmp_path, "--check").returncode == 0

    (tmp_path / "README.md").write_text(
        readme.replace("🟡 Integration blocked", "✅ Accepted", 1), encoding="utf-8"
    )
    stale = run(tmp_path, "--check")
    assert stale.returncode == 1
    assert "table is stale" in stale.stdout


def test_generator_rejects_unknown_status(tmp_path: Path) -> None:
    seed(tmp_path, status_override="almost_done")
    result = run(tmp_path, "--check")
    assert result.returncode == 2
    assert "unsupported task status" in result.stdout


def test_generator_rejects_missing_task(tmp_path: Path) -> None:
    seed(tmp_path)
    data = json.loads((tmp_path / "docs/task-status.json").read_text(encoding="utf-8"))
    data["tasks"].pop()
    (tmp_path / "docs/task-status.json").write_text(json.dumps(data), encoding="utf-8")
    result = run(tmp_path, "--check")
    assert result.returncode == 2
    assert "task order must be exactly" in result.stdout


def test_generator_rejects_missing_plan_anchor(tmp_path: Path) -> None:
    seed(tmp_path)
    plan = (tmp_path / "docs/implementation-plan.md").read_text(encoding="utf-8")
    (tmp_path / "docs/implementation-plan.md").write_text(
        plan.replace('<a id="t04"></a>\n', ""), encoding="utf-8"
    )
    result = run(tmp_path, "--check")
    assert result.returncode == 2
    assert 'exactly one anchor: <a id="t04"></a>' in result.stdout
