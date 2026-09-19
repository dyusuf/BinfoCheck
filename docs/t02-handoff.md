# T02 implementation handoff — 19 September 2026

Task: T02 only / Codex / implementation complete, verification recorded below.
Branch: `codex/t02-text-index`; keep the PR draft and unmerged.
No T03/T04, claims, citation association, retrieval, matching, provider/model calls,
source fetching, API or UI behavior was implemented.

## Inputs, decisions and scope

The user's T02 implementation approval authorizes the text adapter, locked spaCy
dependency, tests, minimal D06/task-status documentation, commits/push and draft PR.
Both main and the dedicated branch were synchronized by fast-forward before editing;
the starting branch was clean at `8538fd6`, identical to origin.

Read AGENTS.md, implementation conventions/T02, architecture shared contracts,
indexing/storage and decision register, MVP exclusions, T00 contracts/validation,
T01 acquisition fixtures/output and T11A protocols/backends. Dependencies T00/T01/T11A
are present. Shared v1 domain wire schemas and validation semantics are unchanged.
No prompts, model configuration or rubrics were added.

D06 is resolved only for T02: **spaCy 3.8.16**, `spacy.blank("de")`, rule-based
Sentencizer and a small versioned abbreviation/decimal/Markdown rule layer.
No language model was downloaded; no parser, NER, transformer or GPU pipeline is used.
The lock includes spaCy's normal CPU runtime dependencies, not just its tokenizer.
T06/T07 corpus parsing, passages, lexical settings, BM25 and RRF remain open.

## Files and contracts

- `pyproject.toml`, `uv.lock`: pin spaCy and lock transitive dependencies.
- `src/binfocheck/text/__init__.py`, `config.py`, `errors.py`: public exports,
  versioned bounded settings and typed/sanitized errors.
- `structure.py`, `sentences.py`, `indexing.py`: bounded block recognition,
  German sentence ranges and `StoredAnswerIndexer` (`AnswerIndexer` protocol).
- `persistence.py`: adapter-owned completion manifest, deterministic IDs/hashes,
  publication/reload and cohort/graph validation through T11A protocols.
- `context.py`: `IndexedContextBuilder` (`ContextBuilder` protocol), returning
  ordered IDs only from a selected completed cohort.
- `verify_saved_capture.py`, component `README.md`: offline copy-first integration
  diagnostic and exact behavior/limits.
- `tests/text/`: `conftest.py`, `helpers.py`, package marker; sentence, structure,
  indexing, context, persistence, graph, saved-copy and acquisition-fixture tests.
- `tests/fixtures/text/README.md`, `v1/sentences.json`: synthetic golden cases.
- `docs/architecture.md`: T02 portion of D06; `docs/implementation-plan.md`:
  T02 status/handoff; this file: verification and limitations.

Commit IDs, draft PR and latest remote CI links are recorded in the PR and final
`/tmp/handoff.txt` delivery record, avoiding a self-referential commit hash here.

## Indexing and context rules

Original answer text is never rewritten, normalized, rendered or searched to select
the first matching quote. All spans are absolute Python Unicode-code-point slices.
ATX/Setext headings, paragraphs, flat list items and their sentence children retain
exact original locations. Sentence edge separator whitespace and bullet markers are
excluded; internal whitespace/punctuation and attached link/citation markers remain.
CRLF, NBSP, tabs, combining characters and emoji remain untouched in the TextRecord.

Common German abbreviations, decimals, dates/selected ordinals and balanced Markdown
regions are protected around spaCy candidates. Unsupported tables, fences, raw HTML,
block quotes, indented code and ambiguous/nested lists are opaque paragraph blocks.
Unsupported inline syntax conservatively remains one sentence span. No markup is
rendered, no URLs fetched and no new citation relationships are inferred.

The index identity hashes the run, observation, original answer ID/content hash,
normalized index settings, index version and spaCy version. Unit identities include
kind and absolute bounds; repeated identical text has different location-based IDs.
Order is start, descending end, kind rank, ID. Timestamps use the immutable run's
creation time. Different configurations/runs produce separate cohorts.

Unit provenance contains only observation and answer IDs. Sentence parents contain
their spans. Nonheadings point to the nearest active heading; headings themselves
have `heading_unit_id=None`. Heading levels/ancestry live in the output manifest.

Completion publication writes artifact metadata, then immutable units, then the
artifact payload. The manifest records ordered IDs/hashes, configuration, input hash,
heading hierarchy, opaque IDs and completion state. It is an output, not a unit input.
Interrupted writes return failures; missing payload/units are incomplete. Identical
offline re-indexing completes partial writes without overwriting history.

Context settings require the exact completion artifact ID. Loading validates its
identity, all unit hashes, ordering, exact spans and run/observation/parent/heading
relationships. It never enumerates units by SQLite insertion order. Defaults are
one preceding/following sentence, heading clipping and heading references included;
overlapping windows deduplicate IDs. Structural targets expand to sentence children;
opaque targets retain their own reference. No neighboring text is stored in context.
Foreign observations/cohorts, corrupt/missing data and limits return typed failures.

## Verification

All required local checks passed:

```text
uv sync --locked --dev                                    passed (60 resolved packages)
uv run --offline --locked pytest tests/text                72 passed
uv run --offline --locked pytest                          466 passed
uv run --offline --locked ruff check .                     passed
uv run --offline --locked ruff format --check .             95 files formatted
uv run --offline --locked pyright                          0 errors / 0 warnings
uv run --offline --locked python -m binfocheck.domain.export_schemas --check
                                                          schemas match
git diff --check                                          passed
```

The full suite retains all 394 existing T00/T01/T11A tests. Formatting was applied
with `uv run --offline --locked ruff format src/binfocheck/text tests/text` before
the final checks. Preliminary checks exposed two Markdown/URL boundary cases and
test-only strict-typing issues; those were fixed before the passing runs above.

Coverage includes 17 explicit sentence golden cases, all four unit kinds, Unicode
locations/repeated text, opaque structures, protocol conformance on memory/SQLite,
determinism/idempotency, restart/context recovery, heading semantics, cross-observation
and cross-configuration rejection, limits, partial publication repair, missing/corrupt
units, rehashed graph corruption, copy-before-open verification and T01 synthetic
normalization with unchanged citation spans. Text tests block socket connections.

## Accepted T01 capture: offline integration only

Command (exit **0**):

```bash
uv run --offline --locked python -m binfocheck.text.verify_saved_capture \
  --source-store /tmp/binfocheck-t01-live-NezU38O1/store \
  --observation-id capture-observation-1c8c8d29e92c00f7f5473716291a185cde1a5f21babfe89841b6aa6c9b857179
```

The complete quiescent private directory was copied before any SQLiteStore open.
All T11A reads/writes and reopen checks used the private copy:
`/tmp/binfocheck-t02-verification-unfmi_r0/store`. The original store was never
opened with SQLiteStore; its file hashes, modification times and modes were unchanged.
Socket `connect`, `connect_ex` and `create_connection` were blocked throughout.

Results:

- Original answer ID:
  `capture-answer-630b1fb95dde23947d0c4df392fdd6897fddcb7701d7ca41f900087159e08119`.
- Answer SHA-256:
  `e6fc250c93791578463a5cc5fe62858536507c9b40ece6cf20dda5a1e64854ba`.
- **3,094 unchanged characters**, **28 units**: 3 headings, 6 paragraphs,
  5 bullets, 14 sentences. All unit spans exactly recover original substrings.
- **10 existing citation spans** still slice the unchanged answer exactly.
- All original records unchanged; source/citation availability remains incomplete.
- Identical re-indexing, close/reopen, full `validate_links` and context reload pass.
  The sampled first-sentence context has 2 ordered unit references, identical after reopen.
- A diagnostic/reanalysis run with zero provider budget exists only in the copy.
  **Zero provider/model calls; zero new provider spend.** No live authorization used.

Only identifiers, hashes/counts and verification status are reported. No real answer,
raw payload, private store, credentials or `.env` are committed. A second earlier
offline verification also passed on a separate copy; neither check touched the source.

## Limitations and remaining decisions

This is deliberately not a CommonMark parser, linguistic correctness proof or claim
extractor. Unrecognized abbreviations may need a later versioned rule change; complex
markup and ambiguous inline regions sacrifice sentence detail rather than source
integrity. Context windows count sentences, not opaque blocks; headings clip by default.
Default index limits are 100,000 characters/10,000 units; context caps targets at 20,
neighbors at 10 per side and output at 200 IDs (configurable within documented bounds).

Publication uses existing immutable storage operations, not a new multi-record
transaction. The final payload is the completion marker; partial units may remain
until identical offline retry. Private-store verification assumes a quiescent source,
not a concurrently written snapshot or crash-durability guarantee. Temporary copies
remain private/outside Git and are ephemeral; no provider call is made if source is absent.

No remaining T02 contract mismatch was found. Remote CI/review status is in the draft
PR/final delivery record. Fresh live/deployed checks are not applicable and were not
run. Remaining D06 decisions belong to T06/T07. Stop here: do not merge or start
T03/T04 or downstream behavior.
