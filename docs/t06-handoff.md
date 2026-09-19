# T06 implementation and capture handoff

Task / assignee / status: **T06 / Codex / offline_passed; live acceptance pending**.
Branch: `codex/t06-corpus`. User authorized implementation, commit/push and a draft
PR, with no merge. The original offline instruction prohibited live requests; the later
bounded user authorization was consumed once as recorded below. No T07 work.

## Current live gate

The authorized capture has completed: six GETs, all complete HTTP 200. The allowance
is consumed. The restricted store and full response/hash/version report are in
[T06 live capture](t06-live-capture.md). Default-profile replay is **failed** with
five `unusable` pages (`ambiguous_article_root`), because the site has no `<article>`
elements. Offline site-profile work from the saved HTML remains before acceptance;
no refetch is needed. Socket-blocked reopen/load/replay passed. Historical offline
and pre-authorization records below describe their respective earlier gates.

## Scope, contracts and decisions

Implemented the approved planning handoff with the user's raw-body clarification:
`ArticleVersion.raw_artifact_id` and `content_sha256` refer to the same complete
HTTP content-decoded HTML bytes **before charset decoding**. Compressed/partial
representations belong to receipts and never substitute for that raw artifact.

Architecture sections 3, 5, 7 and 8 apply. D06's offline T06 selection is recorded
in Architecture: Beautiful Soup **4.15.0**, explicit **html5lib 1.1**,
**llama-index-core 0.14.24**, Python stdlib HTTPS, no LLM/embeddings/retrieval.
Python 3.13.7 and the existing uv toolchain resolved these together with spaCy
3.8.16 and Pydantic 2.13.5; exact transitive dependencies are locked. Runtime corpus
replay checks the three direct corpus package versions. No downloaded NLP model or
NLTK data is used; core's transitive packages do not authorize model/resource calls.

Domain wire schema `1`, validation revision `1.1`, and T11A storage/codec version `1`
are unchanged. No domain/schema/storage-backend/T02 code changes. Supplementary
transport/batch/structure/completion artifacts use existing ArtifactRef/Payload,
SpanRef and T11A protocols; they are not new domain record kinds. No unavoidable
shared-contract blocker arose. The companion lookup/validation convention is
implemented in the corpus module; callers must use its loader to verify readiness.

Build dependencies T00/T11A are present. Synthetic fixtures and new dependencies
were created as T06 deliverables. Live integration depends on later explicit
public-fetch authorization, actual saved page inspection and all-five usability.
T03, embedding settings and T07 are not build dependencies for this offline work.

## Changed files and resulting behavior

- `src/binfocheck/corpus/config.py`, `errors.py`, `receipts.py`, `artifacts.py`:
  exact ordered five-URL allowlist, frozen bounded policy, strict settings, pinned
  versions, canonical identity helpers, supplemental capture artifacts and T11A I/O.
- `capture.py`, `transport.py`: separate injectable capture coordinator and direct
  HTTPS transport denied by default. Start markers prevent repeat dispatch for a
  batch; receipts distinguish dispatched/blocked/uncertain attempts, preserve raw,
  encoded and partial bodies, status/time/headers/counts and redaction metadata.
- `decoding.py`, `parsing.py`, `structure.py`, `passages.py`: deterministic strict
  charset decoding; bounded article-only parsing with versioned chrome/protection
  rules; German wording/Unicode, headings, sections, lists, collapsed FAQ content
  and references preserved; exact structural passages and original DOM locators.
- `llama_adapter.py`: a single explicit mechanical ingestion transformation verifies
  ID/text/offset/source round-trip into nodes with no embeddings, default transforms,
  vector store, docstore, model extraction, resource download or retrieval.
- `ingestion.py`: shared CorpusIngestor implementation replays only saved input,
  creates immutable article/text/passage histories and publishes completion before
  manifest. Loader checks hashes, byte/text lineage, per-URL readiness, receipt and
  predecessor membership, full shared links, and deterministic structure replay.
- `__init__.py`, `__main__.py`, `README.md`: documented API and offline-only CLI for
  replay, inspect and proposed-policy. There is deliberately no live CLI command.
- `tests/corpus/` and `tests/fixtures/corpus/v1/`: authored synthetic German HTML,
  expected text, failure/transport doubles and offline acceptance tests. All five
  pilot URL slots deliberately reuse a synthetic article for wiring tests; these
  are not five real captures or evidence of their real structure/content.
- `pyproject.toml`, `uv.lock`: exact approved parser/core ingestion dependencies.
- `docs/architecture.md`, `docs/implementation-plan.md`, this handoff: decision,
  scope, status, validation and outstanding live gate.

Version names: `t06-corpus-settings/1`, hashed `t06-corpus-parser/1`,
`t06-corpus-passages/1`, `t06-corpus-fetch/1`; companion formats start at 1.
Parser identities include configuration/package pins. Passage construction has its
own version. Fresh capture events make new snapshot identities even for unchanged
bytes; byte artifacts deduplicate. Same saved input/configuration/predecessors
replays identically. Changes append records rather than overwrite old versions.

A succeeded ingestion Outcome can contain an incomplete/failed manifest when
recording page outcomes succeeded. Acquisition failures remain `failed`, captured
but uninterpretable pages remain `unusable`, and only five usable pages with valid
passages can become `ready`. CLI exits nonzero for nonready corpora. Storage or
configuration failures return failed Outcome and preserve already written inputs.

## Offline verification

All required final commands passed on the reviewed implementation; exact results are recorded below. Tests cover:

- Hand-authored exact cleaned output, German qualifiers/Unicode/code-point slices,
  repeated text with distinct locations, heading ancestry/section ranges, explicit
  numbering/nested lists, links and chrome removal with reference protection.
- Strict encoding/conflict/malformed-byte behavior; identity/gzip/deflate bodies;
  compressed representation hashes distinct from exact content-decoded HTML hashes.
- Exact URL membership, robots policy, request spacing/caps/deadlines, no redirects/
  retries/asset requests, host stop, partial bodies, failed/unusable/nonready states.
- Same-input replay, fresh unchanged snapshots, changed content/parser settings,
  immutable predecessor history and same-URL predecessor validation.
- MemoryStore/SQLite persistence and reopen, closed dependency validation, partial
  publication failures, missing/corrupt metadata dependencies and safe offline retry.
- LlamaIndex with forbidden model/default resolvers plus a fresh subprocess that
  blocks sockets/DNS/NLTK downloads before importing and ingesting. No hidden
  collection-time network/resource initialization is assumed safe merely from mocks.
- Offline replay/inspection CLI and explicit absence of a capture CLI.

During development, an invalid CSS selector exposed the library's specific
SelectorSyntaxError rather than Python SyntaxError; this now becomes a typed
configuration validation error. One superseded full-suite run was interrupted
while the corrected final checks were being prepared. Final passing results, not
that partial run, determine offline completion.

## Frozen live-capture proposal — not authorized or executed

Exact URLs, unchanged from MVP and the task:

1. https://www.diabinfo.de/leben/diabetes-im-alltag/strassenverkehr.html
2. https://www.diabinfo.de/leben/diabetes-im-alltag/ramadan.html
3. https://www.diabinfo.de/leben/diabetes-im-alltag/reisen.html
4. https://www.diabinfo.de/vorbeugen/diabetes/wie-hoch-ist-mein-risiko-fuer-diabetes-typ-2/haeufig-gestellte-fragen.html
5. https://www.diabinfo.de/vorbeugen/was-kann-ich-tun/so-erreichen-sie-ihre-ziele.html

The only additional policy request would be
`https://www.diabinfo.de/robots.txt`. Maximum **6 GET dispatches total**: one robots
and one per page; **0 retries, 0 redirects, concurrency 1**, no HEAD/conditional
requests, assets, cookies, credentials, browser, link fetching or substitutions.
Minimum **2 s** between starts; honor longer applicable robots limits. A failed or
uncertain dispatch consumes its request. Robots access failure/unassessable rules
block pages; robots 404/410 permits them. A 429/503 response stops remaining host
requests. Extra attempts require a new bounded instruction.

| Setting | Frozen value |
|---|---|
| Allowed transport | Direct TLS-verified HTTPS to exact www.diabinfo.de paths |
| User-Agent | BinfoCheck-T06/1.0 |
| Request headers | German Accept-Language; identity Accept-Encoding; text/html for pages |
| Connect / read timeout | 10 s / 20 s |
| Request / batch deadline | 30 s / 900 s |
| Received / content-decoded page bound | 5 MiB each |
| Robots bound | 512 KiB |
| Cleaned text / structural blocks | 1,000,000 code points / 20,000 |
| DOM element / nesting bounds | 100,000 / 80 |
| Paid requests / provider cost ceiling | 0 / USD 0 |
| Storage | Operator-configured private T11A SQLite/filesystem root, restricted artifacts |

The deadline watchdog interrupts response trickles after connection. OS DNS
resolution inside stdlib connect is not forcibly interruptible by Python's socket
timeout; do not describe this as a hard real-time resolver guarantee. This known
transport limit must be visible in the later authorization, not hidden by tests.

Later live procedure: record explicit batch-bound authorization; capture once into
T11A; inspect raw saved article containers offline; configure only the structures
actually required by these pages and add synthetic regression examples; replay
without refetching; inspect all text/headings/lists/qualifiers/references on EACH
page, not selected expected matches; check all slices/lineage; close/reopen/replay
with sockets blocked; publish/report a ready corpus only when all five pass the
live acceptance inspection. Report actual IDs, UTC snapshot times, raw/cleaned
hashes, parser/configuration, passage counts, request outcomes and missing data.
No category, overlap finding, citation fidelity or medical assessment is part of it.

## Limitations and stop boundary

The unique-article structural profile is verified against synthetic fixtures only.
Actual diabinfo selectors and accessibility/robots state remain unknown. Tables,
definition lists, unusual list numbering, media and other unsupported essential
structures make the current profile unusable; add only a demonstrated pilot need
with versioned extraction rules, not a generic crawler/readability/CommonMark parser.
Known error titles are rejected, but automated parsing cannot establish that a page
has no partially missing JavaScript-only content. Per-page live inspection remains
mandatory. DOM locators are parsed-tree provenance, not raw-byte spans; exact
passage locations refer to the immutable cleaned TextRecord.

T11A provides immutable individual writes, not a cross-record transaction. Failed
publication may leave unreferenced immutable records/blobs; loader completion
checks prevent treating them as ready. There is no garbage collector, concurrent
capture worker, deployment, new service or power-loss guarantee. No T07 retrieval,
BM25/RRF, embeddings, LLM/Jev, PDFs/video, claim matching or corpus expansion.

## Actual execution and handoff state

Initial requested `git fetch origin`, `git status`, and
`git pull --ff-only origin codex/t06-corpus` passed; branch was clean at
`87808d1a2fccf942a87a8a6d35d99e2daba0faba`. No branch switch. Before final review,
SSH fetches stalled; they were interrupted/bounded by timeout. A per-command HTTPS
rewrite with the existing gh credential helper successfully fetched origin/main;
no remote/global credential configuration was changed. GitHub API independently
reported the same main SHA. No integration merge was needed at that check.

Offline: implemented; final command results below. Live: **not run, not authorized**.
Deployed: **not applicable**. Artifacts: synthetic only; no fresh or replayed real
corpus captures, and no model/rubric IDs. Actual diabinfo requests **0**, robots
requests **0**, model/provider calls **0**, model/provider cost **USD 0**.
Package registry/GitHub development traffic is separate; infrastructure cost is
not measured. Mocks and synthetic fixtures prove wiring, not live compatibility.

Remaining dependency: later bounded public-fetch authorization and successful
five-page inspection/replay. T06 is not accepted and the MVP is not complete.


## Original offline implementation results (`d25b5c7`)

| Command | Actual result |
|---|---|
| `uv sync --locked --dev` | Passed; 103 packages audited |
| `uv run --offline --locked pytest tests/corpus` | 104 passed |
| `uv run --offline --locked pytest` | 570 passed |
| `uv run --offline --locked ruff check .` | Passed |
| `uv run --offline --locked ruff format --check .` | Passed; 121 files already formatted |
| `uv run --offline --locked pyright` | Passed; zero errors/warnings |
| `uv run --offline --locked python -m binfocheck.domain.export_schemas --check` | Passed; schemas match |
| `git diff --check` and `git diff --cached --check` | Passed |

The final ingestion regression also checks that complete non-HTML error bodies
remain receipt artifacts and do not populate article raw-HTML/hash fields. No tests
were weakened. Offline acceptance is passed; live integration remains deliberately
unperformed. Commit/push and draft PR delivery are authorized; no merge is authorized.


## Pre-live authorization review follow-up

The user reviewed `d25b5c7` and draft PR #7, confirmed hosted CI passed on that exact
head, and accepted the offline review. The requested follow-up binds live approval
to the exact frozen configuration and fixes the stale T02 status to accepted/merged.
The capture configuration, package pins, corpus output contracts and live gate are
unchanged. No real diabinfo/robots or model requests were made during this fix.

`LiveAuthorization.policy_sha256` is required with no automatic default. The
`t06-live-authorization/1` envelope hashes canonical sorted UTF-8 JSON containing
`format`, `robots_url`, ordered `page_urls` and the complete `fetch_policy` object.
The digest to record in any later explicit approval of the current proposal is:

```text
78de13b54502cf2c8395d9be1301f66c74bbe0d8b8cf5a931f58e71c1aad5d18
```

Carry that approved value into the authorization; do not recompute the field to
refresh an older approval after configuration changes. `proposed-policy` now prints
the robots URL and digest while retaining `authorized: false`. Both capture preflight
(before a start artifact) and every HTTPS request (before connection construction or
counter increment) reject a mismatching digest with `live_policy_not_authorized`.
The existing batch binding and absence-of-approval checks remain in place.

New offline tests exercise every policy field, all five URLs, order/membership,
robots URL, stale/malformed/empty digests, unchanged batch IDs, no storage/network
side effects on rejection, and a second-request policy change. Existing fake HTTPS
success tests use a matching digest. No T00 schemas or dependencies changed.
Follow-up implementation commit: `702af5e`. Before final review, `origin/main`
advanced to `80b35c95daaf06bfe9149551068d609e39d4ab58` (T03 / PR #6).
That revision was merged into this branch. Dependency conflicts retain all three
T06 exact pins and T03's promotion of `jsonschema` to a runtime dependency;
`uv lock --offline` resolved the same 103 packages. T03 code, fixtures and decision
records are preserved. A subsequent fetch confirmed main remained at that revision.

All required checks passed again on the combined implementation:

| Command | Result |
|---|---|
| `uv sync --locked --dev` | Passed; 103 packages resolved |
| `uv run --offline --locked pytest tests/corpus` | 132 passed |
| `uv run --offline --locked pytest` | 719 passed |
| `uv run --offline --locked ruff check .` | Passed |
| `uv run --offline --locked ruff format --check .` | Passed; 145 files formatted |
| `uv run --offline --locked pyright` | Zero errors/warnings |
| `uv run --offline --locked python -m binfocheck.domain.export_schemas --check` | Schemas match |
| `git diff --check` / staged whitespace check | Passed |

Delivery remains draft [PR #7](https://github.com/dyusuf/BinfoCheck/pull/7),
with no merge to main. The original head's hosted CI was confirmed by user review;
new-head CI is tracked separately from these completed local checks. Offline review
passes; live acceptance remains pending. No diabinfo/robots/model calls, paid usage
or deployed checks were performed during this follow-up. The frozen six-GET proposal
above remains unapproved; the required digest does not itself grant authorization.

## Authorization evidence follow-up

The user confirmed exact-head hosted CI green on `e18faa86fc31ee8a1109864071e8dd37256cff33`
with 719 tests, and requested persistence of the explicit approval envelope before
any live capture. This follow-up adds restricted immutable
`<batch-id>.authorization.v1` using T11A ArtifactRef/Payload storage. Its format is
`t06-live-authorization/1`; fields preserve batch ID, approval reference, policy
SHA-256, robots URL, ordered five page URLs and complete FetchPolicy.

Capture validates the envelope first, writes and reads it back before the start
marker, then dispatches. CaptureStart links `authorization_artifact_id`; ingestion
includes that artifact in the completion dependency graph. Both replay and load
check the start linkage, batch identity, nonblank approval reference, restricted
access, exact frozen policy and its digest. Missing/invalid evidence prevents live
replay/readiness. Synthetic captures have no authorization link; existing synthetic
start markers remain readable. Live origin cannot be supplied through an
unauthenticated custom transport. Offline tests use an explicit HTTPS subclass
with synthetic responses and no sockets; these are not real live captures.

Failures saving authorization or the start marker dispatch nothing. If interrupted
after writing the envelope, its immutable ID prevents replacement by a different
approval. Successful SQLite reopen/replay retains the exact approval reference and
policy. Tests also reject missing evidence, wrong batch/reference/digest/robots/
ordered URLs/policy and missing start linkage, and cover immutable orphan evidence.

No T00/shared schema, package, parser, fetch policy or digest change. D06 and corpus
README record the companion convention. The complete frozen proposal above remains
unapproved, including its digest
`78de13b54502cf2c8395d9be1301f66c74bbe0d8b8cf5a931f58e71c1aad5d18`.
No diabinfo, robots, provider/model requests, paid usage or deployed checks occurred.
Latest main was fetched and remained `80b35c95daaf06bfe9149551068d609e39d4ab58`,
already included in this branch. T07 remains outside this task.

Validation for the authorization evidence follow-up:

| Command | Result |
|---|---|
| `uv sync --locked --dev` | Passed; 103 packages audited |
| `uv run --offline --locked pytest tests/corpus` | 145 passed |
| `uv run --offline --locked pytest` | 732 passed |
| `uv run --offline --locked ruff check .` | Passed |
| `uv run --offline --locked ruff format --check .` | Passed; 146 files formatted |
| `uv run --offline --locked pyright` | Zero errors/warnings |
| `uv run --offline --locked python -m binfocheck.domain.export_schemas --check` | Schemas match |
| `git diff --check` / staged whitespace check | Passed |

All checks were offline; a final fetch confirmed main had not advanced. Draft PR #7
is the delivery target and must not be merged by this task. Exact-head hosted CI
for this new commit is reported separately from the completed local checks.
