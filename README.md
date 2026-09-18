# BinfoCheck

BinfoCheck measures citations and content overlap with diabinfo.de. It does not
establish AI provenance or provide medical advice. This repository currently
implements **T00: shared contracts, synthetic examples and tooling**.

## Setup

Use uv (verified with 0.8.23). `.python-version` pins CPython 3.13.7; the package
targets Python 3.13. Install uv before running:

```bash
uv sync --locked --dev
```

Initial setup may download Python and locked dependencies. Pyright's Node runtime
is included through its `nodejs` extra so checks do not bootstrap Node from the
network. Pydantic v2 is the runtime dependency; pytest, Ruff, Pyright, jsonschema
and its typing stubs are development dependencies. jsonschema checks exported
schemas and structural fixture compatibility.

## Offline checks

Run from the repository root after setup:

```bash
uv run --offline --locked pytest
uv run --offline --locked ruff check .
uv run --offline --locked ruff format --check .
uv run --offline --locked pyright
uv run --offline --locked python -m binfocheck.domain.export_schemas --check
git diff --check
```

Tests block socket connections and need no credentials or providers. Ruff and
Pyright are configured in `pyproject.toml`; Pyright uses strict checking.

## Contracts

Python models live in `src/binfocheck/domain/`. Records use schema version `1`.
Import concrete types from their domain modules; `Record`, `RecordSet` and
`validate_links` are also exported by `binfocheck.domain`.

Use `model_validate_json` (or `RECORD_ADAPTER.validate_json` for a record union)
at JSON boundaries. Python construction is strict: pass actual enum members,
UTC datetimes and tuples, rather than expecting coercion. Models reject unknown
fields. Serialization uses `model_dump_json`, retaining nulls and defaults.

Local Pydantic validation checks record shape and state consistency. Separately,
`validate_links(RecordSet(...))` checks a complete bundle's references, run and
observation membership, exact source spans, and history. It raises `LinkError`
with a stable error code and owning record ID. It does not locate quotes, select
context, route citations, judge evidence or execute pipeline stages.

Offsets count Unicode code points in unchanged saved text, with an exclusive end.
Repeated wording is identified by explicit offsets and, where supplied, the source
unit. Available-empty, incomplete and unavailable data are distinct. Model usage
can remain unknown; unknown is never converted to zero. Decision and generation
outputs have distinct discriminated result shapes within `DecisionRecord`.

Finding replacements and review corrections use new IDs and explicit supersession
links. Prior records remain present. A finding history has one terminal selection
per claim/run. Reviews remain separate events and cannot rewrite a finding.

Query, reviewer, provider-request, model, configuration/version, duplicate-group,
claim-group, storage-key and work-key identifiers name external entities or labels;
they are not local record references. Index metadata is embedded and checked
against its corpus and retrieval batch. Captures and corpus versions are inputs;
analysis-derived records carry `analysis_run_id`.

## Schemas and examples

`schemas/v1/` contains generated JSON Schemas. Regenerate after an authorized
contract change:

```bash
uv run --offline --locked python -m binfocheck.domain.export_schemas
```

The check compares complete deterministic exports and detects missing, changed or
extra JSON files. Schemas derive from Python types; never edit them by hand.
Custom semantic validators and cross-record relationships are enforced by Python,
not fully expressible in JSON Schema. Schema validation alone is insufficient.

`tests/fixtures/contracts/v1/` contains only labeled synthetic examples. The
manifests enumerate every record and boundary's valid/invalid/missing-data coverage.
`linked.json` is a complete linked graph, not a persistence format. Its model/rubric
labels are placeholders; no prompts or business rubrics are implemented.

Component interfaces and storage interfaces are protocols. `tests/doubles/`
contains scripted responses that check fixture requests and record calls; it has
no database, file storage or write semantics. T11A owns persistent storage and
durability. Provider/model integrations and all downstream behavior remain outside
T00.
