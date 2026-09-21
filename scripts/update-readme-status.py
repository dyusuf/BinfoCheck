#!/usr/bin/env python3
"""Generate or verify README's public task-status table from docs/task-status.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

START = "<!-- TASK-STATUS:START -->"
END = "<!-- TASK-STATUS:END -->"
EXPECTED_TASKS = (
    "T00",
    "T11A",
    "T01",
    "T02",
    "T03",
    "T04",
    "T05",
    "T06",
    "T07",
    "T08",
    "T09",
    "T10",
    "T11B",
    "T12",
    "T13",
    "T14",
)
STATUS_LABELS = {
    "not_started": "⚪ Not started",
    "in_progress": "🔵 In progress",
    "offline_passed": "🟠 Offline passed",
    "integration_blocked": "🟡 Integration blocked",
    "accepted": "✅ Accepted",
}


def load_status(path: Path) -> list[dict[str, str]]:
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read {path}: {error}") from error
    if not isinstance(raw, dict) or raw.get("version") != 1 or set(raw) != {"version", "tasks"}:
        raise ValueError("task-status.json must contain only version=1 and tasks")
    tasks = raw["tasks"]
    if not isinstance(tasks, list):
        raise ValueError("tasks must be a list")

    normalized: list[dict[str, str]] = []
    for item in tasks:
        if not isinstance(item, dict) or set(item) != {"id", "component", "status"}:
            raise ValueError("each task must contain exactly id, component, and status")
        task_id, component, status = item["id"], item["component"], item["status"]
        values = (task_id, component, status)
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError("task id, component, and status must be non-empty strings")
        if status not in STATUS_LABELS:
            raise ValueError(f"unsupported task status: {status}")
        normalized.append({"id": task_id, "component": component, "status": status})

    ids = tuple(item["id"] for item in normalized)
    if ids != EXPECTED_TASKS:
        raise ValueError(f"task order must be exactly: {', '.join(EXPECTED_TASKS)}")
    return normalized


def render(tasks: list[dict[str, str]]) -> str:
    lines = [
        START,
        "| Task | Component | Status |",
        "|---|---|---|",
    ]
    lines.extend(
        f"| {item['id']} | {item['component']} | {STATUS_LABELS[item['status']]} |"
        for item in tasks
    )
    lines.append(END)
    return "\n".join(lines)


def expected_readme(readme: str, generated: str) -> str:
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("README must contain exactly one task-status marker pair")
    start = readme.index(START)
    end = readme.index(END, start) + len(END)
    if end <= start:
        raise ValueError("invalid README task-status markers")
    return readme[:start] + generated + readme[end:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail instead of updating on drift")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    root = args.root.resolve()
    status_path = root / "docs/task-status.json"
    readme_path = root / "README.md"
    try:
        tasks = load_status(status_path)
        current = readme_path.read_text(encoding="utf-8")
        wanted = expected_readme(current, render(tasks))
    except (OSError, ValueError) as error:
        print(f"task-status error: {error}")
        return 2

    if args.check:
        if current != wanted:
            print("README task-status table is stale; run scripts/update-readme-status.py")
            return 1
        print("README task-status table is current.")
        return 0

    if current != wanted:
        readme_path.write_text(wanted, encoding="utf-8")
        print("Updated README task-status table.")
    else:
        print("README task-status table already current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
