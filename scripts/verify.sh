#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

UV_OFFLINE=1 uv sync --locked --dev
uv run --offline --locked pytest
uv run --offline --locked ruff check .
uv run --offline --locked ruff format --check .
uv run --offline --locked pyright
uv run --offline --locked python -m binfocheck.domain.export_schemas --check
git diff --check
git diff --cached --check
