# T11A handoff — shared record and artifact storage

Task / assignee / status: T11A / Codex / implementation complete; local and hosted
checks passed; draft PR [#2](https://github.com/dyusuf/BinfoCheck/pull/2) awaits review.
Branch: `codex/t11a-storage`. No merge performed.

## Scope and decisions

Build dependency T00 is accepted. D02 selects standard-library SQLite metadata and
content-addressed local artifact files behind the existing T00 protocols. This work
implements only T11A, under Architecture Sections 3, 7, and 8. Domain wire schema
`1` and validation revision `1.1` are unchanged; storage schema and codec start at
version 1. No dependency, CI configuration, or domain schema changes.

The user's implementation approval adjusts the plan: cursors are unsigned (no HMAC
or keys); persistence tests close/reopen stores (no process-kill/power-loss tests);
schema handling initializes v1 and rejects foreign/unsupported versions (no future
migrations); artifact access labels remain metadata (no user authorization).

## Changed files

- `src/binfocheck/storage/__init__.py`: public backend/initialization-error exports.
- `src/binfocheck/storage/base.py`: typed protocol operations and lifecycle helpers.
- `src/binfocheck/storage/sqlite.py`: SQLite metadata, immutable transactions, lookup,
  bounded listing, and filesystem integration.
- `src/binfocheck/storage/memory.py`: stateful parity backend with isolated values.
- `src/binfocheck/storage/blobs.py`: verified digest paths, no-follow traversal,
  no-replace publication, and handled temporary-file cleanup.
- `src/binfocheck/storage/codec.py`: canonical serialization and read integrity checks.
- `src/binfocheck/storage/cursors.py`: versioned continuation/filter/position checks.
- `src/binfocheck/storage/errors.py`: fixed typed/sanitized error outcomes.
- `src/binfocheck/storage/migrations.py`: transactional schema-v1 initialization only.
- `src/binfocheck/storage/README.md`: configuration, guarantees, and limitations.
- `tests/storage/__init__.py`, `conftest.py`, `helpers.py`: backend parametrization,
  protocol typing, synthetic payloads, and assertions.
- `tests/storage/test_conformance.py`: shared backend acceptance tests.
- `tests/storage/test_sqlite.py`: persistence, filesystem/failure, and schema tests.
- `docs/implementation-plan.md` and this handoff: task status and completion record.

## Acceptance results

| Requirement | Demonstrated result |
|---|---|
| Restart recovery | Save all 27 existing linked records and both artifacts, close/reopen SQLite, recover equal typed/JSON values, IDs, text, Unicode spans, nulls, availability, decisions, findings, and reviews; `validate_links` passes. |
| Immutability | Identical retries retain one record row; different canonical content or kind conflicts without overwriting; new IDs permit new versions. |
| Artifact integrity | Strict base64 and SHA-256 checks; digest-derived paths; verified deduplication; missing/corrupt bytes return typed failures; empty bytes remain valid. |
| Write safety | Publication sees complete bytes before metadata commit; file/publication/metadata/commit failures roll back records and clean temporary files where practical; orphan complete blobs can be reused. Symlink/path-escape tests pass. |
| Lookup | Correct typed records/payloads; `not_found` for absent IDs; `artifact_data_missing` for metadata without bytes; empty queries succeed with empty pages. |
| Listing | Bounded deterministic insertion order, fixed traversal high-water mark, no duplicates/skips, continuation after reopen, and explicit invalid/foreign/filter/position cursor errors. |
| Append history | Decisions/reviews use immutable inserts, including generic writes; retries do not duplicate history, conflicts preserve originals, and new IDs preserve superseding events. |
| Schema | Empty initialization and current reopen pass; foreign/newer/unsupported-codec rejection and initialization rollback pass. |
| Memory parity | Both backends pass the same core write/read/conflict/list/artifact/append tests; mutable input/output children cannot alter stored records. |
| Errors | Fixed messages contain no SQL, payloads, credentials, or internal paths; busy/locked is retryable, validation/conflict is not. |
| Scope | No provider/model calls, ingestion, retrieval, orchestration, API/UI, authorization, T11B, or downstream behavior. T00 wire schemas unchanged. |

## Pre-merge root-permission review

The review identified that `mkdir(mode=0o700, exist_ok=True)` does not change an
existing directory's permissions. `SQLiteStore` now rejects any group/other
permission bits with non-retryable `StorageInitializationError` code
`insecure_storage_permissions`, before opening or creating SQLite. It does not
chmod operator-owned paths or modify existing data on rejection. New roots remain
private (`0700`), and private existing stores reopen normally.

Ten additional cases cover `0755`, `0750`, `0707`, and `0777` roots, both empty and
populated; assert SQLite is never opened and data/permissions remain unchanged;
and verify new/private-existing root creation and recovery. Changes are limited to
`storage/sqlite.py`, its README, `tests/storage/test_sqlite.py`, and this handoff.
This is local filesystem protection, not T12 user authorization or an ACL audit.

After the fix, the branch was rebased without conflicts onto `origin/main`
(`e1fbae1`); its two README-only commits are preserved. All local commands below
are rerun after that rebase. No downstream code or domain contract changed.

## Commands actually run

| Command | Final local result |
|---|---|
| `uv sync --locked --dev` | Passed; locked environment unchanged. |
| `uv run --offline --locked pytest tests/storage` | 90 passed after review/rebase. |
| `uv run --offline --locked pytest` | 266 passed after review/rebase, including all 176 existing T00 tests. |
| `uv run --offline --locked ruff check .` | Passed. |
| `uv run --offline --locked ruff format --check .` | Passed; 52 Python files formatted. |
| `uv run --offline --locked pyright` | Passed; zero errors/warnings. |
| `uv run --offline --locked python -m binfocheck.domain.export_schemas --check` | Passed; generated contracts match committed schemas. |
| `git diff --check` and `git diff --cached --check` | Passed. |

Formatting/lint autofix commands were also run on `src/binfocheck/storage` and
`tests/storage`. Development iterations corrected formatting/types and an incorrect
test assumption that canonical JSON preserves dictionary insertion order; typed
values and exact strings remain preserved. The first sandboxed uv invocation could
not access its existing cache; required checks succeeded with approved cache access.

Hosted integration: GitHub Actions [run 35410034823](https://github.com/dyusuf/BinfoCheck/actions/runs/35410034823)
passed for original pre-rebase implementation commit `cd3a977`; the original handoff
head also passed [run 35410195699](https://github.com/dyusuf/BinfoCheck/actions/runs/35410195699).
The reviewed/rebased branch is checked by the same workflow; its current result is in
[PR #2 checks](https://github.com/dyusuf/BinfoCheck/pull/2/checks).

Offline checks: passed. Hosted CI: implementation passed, current-head check linked
above. Live provider and deployed checks: not applicable to T11A and not run.
No provider/model calls were made; usage/cost from such calls is zero.

## Artifacts, limitations, and remaining work

Inputs are the existing synthetic `tests/fixtures/contracts/v1/linked.json` and
existing valid/unavailable record variants. The two synthetic artifact payloads are
UTF-8 `Äpfel 🍎 sind rot. Äpfel 🍎 sind rot.` (no newline) and `{}`, matching their
existing hashes. There are no fresh live captures or new model/rubric versions.

- Root configuration and SQLite files are operator-controlled; filesystem support
  is Linux/POSIX local storage. Artifact public inputs cannot supply arbitrary paths.
- `storage_key` is metadata. `restricted` does not implement authorization; T12/D10
  must add access controls. Callers must redact credentials before storing payloads.
- Cursors are opaque continuation state, not authenticated/tamper-proof tokens.
- Individual writes validate local contracts; complete linked validation is explicit
  because the domain graph contains cycles. No new batch protocol was introduced.
- SQLite/filesystem writes are not one transaction. Handled failures can leave a
  complete unreferenced blob. No garbage collection, power-loss guarantee, process
  simulations, or network-filesystem durability claim is included.
- Separate store instances handle bounded SQLite writer contention. No stress or
  concurrency infrastructure was added; instances are used on their creating thread.
- No schema migration framework or speculative upgrade path exists.

No implementation blocker or unresolved D02 ambiguity remains. Review is pending;
stop here before T11B or any other downstream task.
