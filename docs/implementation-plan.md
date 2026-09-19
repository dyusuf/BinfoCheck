# BinfoCheck — Implementation Plan

**Version:** 1.4 · 19 September 2026  
**Status:** T00 and T11A accepted. T01 live and offline acceptance passed. T02 is accepted and merged; T06 five-page textual corpus live acceptance passed under the approved D06 visual-limitation rule; PR #7 is merged.

[MVP](mvp.md) owns scope; [Architecture](architecture.md) owns contracts and technical
rules; this plan assigns work. [Beyond MVP](beyond-mvp.md) lists deferred work.

## 1. Task readiness

**Build dependencies** enable development with fixtures/doubles. **Integration
dependencies** enable checks with real upstream components, storage and providers.
A live extractor need not block retrieval development. Missing artifacts are not
blockers when creating them is part of the task; missing prerequisites outside the
task block only dependent work.

Statuses: `not_started`, `in_progress`, `offline_passed`, `integration_blocked`,
`accepted`. Accept a task only after its required checks pass. Record the assignee,
schema/rubric versions, blockers and check results in the handoff.

Resolve [D01–D10](architecture.md#8-decision-register) under the architecture's decision
rule. Use recorded task/user authorization, not an assumed approval role. Propose any
unresolved choice that blocks the assigned work and request user direction unless
the task delegates that choice. Continue unblocked work.

## 2. Shared rules

Follow root [AGENTS.md](../AGENTS.md) for reading, authorization, safety, testing and
reporting, and [Development workflow](development-workflow.md) for task isolation,
delivery and cleanup. No downstream work or substitutions outside the recorded scope.

Paths are relative to planned `src/binfocheck/`, except `frontend/`, `tests/`, `docs/`,
`prompts/`, `rubrics/` and project/deployment configuration. T00 establishes them.
**T00 creates shared contracts**; later changes need explicit task or recorded-decision
authorization, version updates and consumer tests. Other branches must not duplicate schemas.

Tests are offline by default. Label synthetic fixtures, saved captures and doubles.
Live checks require authorized limits and T11A storage; credentials are not permission
to spend. Use the architecture's source, status and decision rules in every task.

Global exclusions: citation fidelity, medical advice, extra alternative-source
fetching/search, multi-model voting, systematic benchmarks and calibration. Reading
relevant public technical documentation is allowed under AGENTS.md. Basic correctness
and live integration checks remain required. Scope changes need explicit task/user
authorization recorded in the project documents.

## 3. Build sequence

| Stage | Tasks |
|---|---|
| Foundation | T00 contracts → T11A shared persistence |
| Inputs | T01 acquisition, T02 indexing, T03 models, T06 corpus; offline work may run in parallel after T00 |
| Analysis | T04/T05 extraction/citations; T07 retrieval independently; T08 → T09 → T10 evidence decisions |
| Product | T11B execution, T12 API, T13 dashboard; develop against contracts, then integrate |
| Completion | T14 offline replay, live pipeline and deployed review |

T11A comes early deliberately; do not defer all storage until after model work.

## 4. Task cards

Each card lists dependencies, tools, owned files, required checks and a stop boundary.
All listed checks are acceptance requirements; a blocked live check permits reporting
offline progress, not full acceptance.

### T00 — Shared contracts, examples, scaffold and CI

**Build:** repository scope/design documents. **Integrate:** GitHub Actions CI. **Decisions:** D01.  
**D01 resolved for T00:** Python 3.13; uv; Pydantic v2; pytest; Ruff; Pyright.  
**Tools / files:** Python schema/test tooling; `domain/`, `schemas/v1/`,
`tests/fixtures/contracts/v1/`, project configuration, README, and
`.github/workflows/ci.yml`.

Implement Architecture Section 3's records/interfaces, including storage interfaces
and doubles—not a backend. Export JSON Schemas from the Python domain types into
`schemas/v1/`. Establish reproducible setup, offline tests, linting, formatting,
type checking, schema-drift checks, and a minimal GitHub Actions workflow.

CI must run on pushes and pull requests to `main`, use Python 3.13 and the locked uv
environment, and require no provider/model credentials or live/paid calls.

**Checks:**
1. Every boundary has valid, invalid-with-error and applicable unavailable-data
   examples. A linked observation → claim → finding → review resolves all IDs.
   Storage interfaces/doubles exist, but persistent storage remains T11A.
2. Serialization preserves IDs, nulls, enums and availability; invalid spans/statuses
   and invalid linked-record relationships fail rather than being repaired. Schema
   exports agree with the Python types. `Äpfel 🍎 sind rot.` sliced `[8:17]`
   yields `sind rot.`; repeated text is disambiguated by location.
3. These local checks pass:
   - `uv sync --locked --dev`
   - `uv run --offline --locked pytest`
   - `uv run --offline --locked ruff check .`
   - `uv run --offline --locked ruff format --check .`
   - `uv run --offline --locked pyright`
   - `uv run --offline --locked python -m binfocheck.domain.export_schemas --check`
   - `git diff --check`

   GitHub Actions runs the same offline quality checks on push/PR to `main`; the first
   CI run must pass before T00 is accepted.

**Stop:** provider calls, Jev/hosted-LLM calls, claim extraction, citation mapping,
corpus ingestion, retrieval, evidence classification, persistent storage, API, UI,
or future-only fields. Do not start T11A or downstream tasks.

**T00 handoff — 18 September 2026 / Codex / accepted (including added CI gate)**

- Authorization: user's explicit T00 approval, including `schemas/v1/`, storage
  interfaces/doubles only, and the six contract clarifications. D01 is resolved in
  Architecture Section 8; D02 and all downstream decisions remain untouched.
- Scope/versions: Architecture Sections 3, 7 and 8; schema `1`; synthetic fixtures
  `tests/fixtures/contracts/v1/`, including `obs-1`, `claim-1`, `finding-1`,
  `review-1` and `review-2`. Model/prompt/rubric labels are synthetic placeholders.
- Files: `src/binfocheck/domain/` records, protocols, linked validation and exporter;
  package initializers; `schemas/v1/` (64 generated schemas); `tests/contracts/`,
  `tests/doubles/`, `tests/fixtures/contracts/v1/`, `tests/conftest.py`; `README.md`,
  `.gitignore`, `.python-version`, `pyproject.toml`, `uv.lock`; D01 and this handoff.
- Dependencies: Python 3.13.7, uv 0.8.23; exact package versions in `uv.lock`.
  Build dependencies installed; GitHub Actions CI passed. Pyright's Node runtime
  is installed with development dependencies for offline checks.
- Required commands actually run and passed: `uv sync --locked --dev`;
  `uv run --offline --locked pytest` (134 passed);
  `uv run --offline --locked ruff check .`;
  `uv run --offline --locked ruff format --check .`;
  `uv run --offline --locked pyright` (zero errors/warnings);
  `uv run --offline --locked python -m binfocheck.domain.export_schemas --check`;
  `git diff --check`. Setup also ran `uv lock`; formatting/import fixes and schema
  generation ran before the final checks.
- Acceptance: all 10 original user criteria and the added CI gate passed.
  All 20 record types and 21 operations have fixture coverage; linked IDs resolve;
  round trips retain meaning; malformed
  states/spans/relationships fail; Unicode/repeated locations pass; schema drift is
  detected; protocols and scripted doubles type-check. History remains separate.
- Offline: passed. Live/deployed: not applicable to T00, not run. All artifacts are
  synthetic; no provider/model requests were made, so live usage/cost is zero.
- CI follow-up: `.github/workflows/ci.yml` now defines the required push/PR-to-main
  checks using pinned actions, Python 3.13.7 and uv 0.8.23 with locked dependencies.
  README documents the workflow. No provider/model credentials or calls are needed.
  All seven local commands were rerun successfully (134 tests); workflow YAML,
  triggers, permissions, action pins and command list were validated locally.
  First hosted [CI run 35404372636](https://github.com/dyusuf/BinfoCheck/actions/runs/35404372636)
  passed all steps for commit `0d98df593ade8f59e4ca2c9d87f2e997b6ed75d8` on
  [PR #1](https://github.com/dyusuf/BinfoCheck/pull/1).
- Remaining T00 work/blockers: none. T11A is not started. No persistent backend
  or downstream behavior was implemented. Commits, branch publication and PR
  creation were explicitly authorized by the user; the PR has not been merged.
- Pre-merge review: contract validation revision `1.1` strengthens citation capture
  integrity, answer/article provenance, nonblank successful answers, and complete
  probability distributions (Architecture Section 8). Adds 42 focused cases in
  `tests/contracts/test_review_integrity.py`; all seven required local commands pass,
  including 176 tests. The v1 wire shape
  is unchanged; generated schemas include the probability constraint description.

### T11A — Shared record and artifact storage

**Build:** T00. **Integrate:** selected persistent backend. **Decisions:** D02.  
**Tools / files:** storage code; `storage/`, migrations if needed, storage tests.

Implement T00's storage contract with test and persistent backends: immutable
artifacts, typed records, ID lookup, bounded listing, hashes/versions and append-only
model decisions/reviews.

**Checks:**
1. Save a linked fixture; restart and recover identical text, IDs, spans and history.
2. Repeated local writes do not duplicate records. Different content under an
   immutable ID fails; a new ID permits a new version.
3. Failed writes return errors. Integration records use this store without secrets
   or unrestricted artifact-download paths.

**Stop:** scheduling, orchestration, API and UI; T11B owns execution.

**Handoff:** [T11A implementation, checks, and limitations](t11a-handoff.md).
Draft PR #2 is awaiting review; no downstream work started.

### T01 — Acquire a Google AI Mode observation

**Build:** T00 + labeled provider fixtures. **Integrate:** T11A + DataForSEO.  
**Decisions:** D03. **Tools / files:** Python HTTP adapter; `acquisition/`, its fixtures/tests.

Implement capture and replay through the selected endpoint. Preserve raw response,
observation identity, answer, references/excerpts, settings and outcomes. A payload's
`ai_overview` item does not change the Google AI Mode product identity.

**Checks:**
1. Save one authorized successful live capture; replay normalization with identical
   observation identity/answer. Mark unsupported metadata explicitly.
2. Incomplete citations remain incomplete, empty-but-assessable remains empty, and
   a URL/reference is not invented as an inline citation or claim mapping.
3. Authentication failures, rate limits and absent answers have typed outcomes, not
   empty successes. Retries obey limits and retain available request IDs/usage.

**Stop:** extraction, source fetching, browser automation or extra products.
Offline replay alone is not live acquisition acceptance.

**T01 status — 19 September 2026: accepted.** One authorized Google AI Mode live
capture passed persistence, budget verification and network-blocked offline replay;
128 acquisition tests and 394 total tests pass. Cost USD 0.004; one POST, zero retries.
See [T01 handoff](t01-handoff.md). The one-call authorization is consumed; future
provider requests require new explicit authorization. PR remains draft and unmerged.

### T02 — Index answers and reconstruct context

**Build:** T00 + answer fixtures. **Integrate:** T01 output + T11A. **Decisions:** D06.  
**Tools / files:** code, spaCy 3.8.16 blank German tokenizer/Sentencizer; `text/`, text tests.

Index headings, paragraphs, bullets and sentences against unchanged text/citation
locations. Reconstruct neighboring context by ID, allowing multiple sentences but
never crossing observations. Do not duplicate neighbor text in records.

**Checks:**
1. German abbreviations, decimals, bullets, repeated text and emojis have expected
   boundaries; all spans recover exact original text.
2. Context returns the expected ordered references; repeated sentences retain
   distinct locations without duplicated context storage.
3. Index/reload a real capture unchanged. Reuse the German/emoji fixture in T13.

**Stop:** claim generation, citation association or matching. Sentences are not claims.

**Handoff:** [T02 implementation, offline capture verification and limitations](t02-handoff.md).
Implementation and local acceptance are complete; remote review/CI status is recorded
in the draft PR and final delivery handoff. No new provider call is authorized.

### T03 — Decision and generation adapters

**Build:** T00 + request/response doubles. **Integrate:** T11A + Jev + hosted LLM.  
**Decisions:** D04 + live budget. **Tools / files:** selected HTTP/SDK integrations;
`models/decision.py`, `models/generation.py`, adapter tests/configuration.

Separate fixed-choice/probability decisions from generated structured text. Save
model identities, artifacts, prompt/config versions, timing, usage and failures as
DecisionRecords. No undisclosed fallback.

**Checks:**
1. Reject unknown labels, malformed output and missing/invalid required probabilities.
   Valid output serializes; missing usage remains unknown.
2. Retry tests stop at limits without fabricated results. No Jev access means blocked
   integration, not permission to substitute.
3. Persist one authorized live request per selected adapter with contract-valid output
   and actual usage where available. This is not a performance claim.

**Stop:** business rubrics, extraction policies, comparisons and calibration.

**T03 status — 19 September 2026:** offline passed; Jev live integration passed
with exactly one authorized request and zero retries using `jev-1.13.0`.
OpenAI Responses `gpt-4.1-mini-2025-04-14` remains offline-tested only: live
integration is blocked because credentials/API access are unavailable, and the
user explicitly skipped that live smoke. T03 remains partially integrated, with
OpenAI as an outstanding integration dependency; it is not fully live-accepted.
**Handoff:** [T03 files, checks, frozen smoke payloads and limitations](t03-handoff.md).

### T04 — Claimify-inspired ClaimExtractor

**Build:** T00, T02, T03 contracts/doubles. **Integrate:** T01, T03 live, T11A.  
**Decisions:** D07. **Tools / files:** code/Jev/hosted LLM per Architecture Section 4;
`claims/`, `prompts/extraction/`, `rubrics/extraction/`, extraction tests.

Implement selection, ambiguity handling, clarification and decomposition. Code
locates original quotes; Jev checks extraction against original context. Keep German
claims and separate rejected/unresolved issues.

**Checks:**
1. Controlled multi-fact and multi-sentence examples retain correct spans/context IDs.
   Repeated quotes need a unique location or become issues.
2. Invented quotes fail. Changed qualifications cannot silently pass validation;
   uncertainty/errors stay recorded. The question cannot supply a new fact.
3. Process a saved real answer using live adapters. Save claims, issues, originals
   and decision versions; manually inspect and report errors, not an accuracy rate.

**Stop:** citation fidelity, corpus matching or claims of reproduced Claimify quality.

**Status:** Offline implementation and acceptance fixtures completed. Live integration
is blocked by unavailable GenerationModel access and absent request-bound authorization.
Check 3 remains outstanding; T04 is not fully accepted. Shared contracts and T03 remain
unchanged; extraction-only D07 resources are selected.

### T05 — Citation mapping and routing

**Build:** T00 + provider/claim fixtures. **Integrate:** T01, T04, T11A.  
**Decisions:** D07. **Tools / files:** code/metadata; `citations/`, mapping rules/tests.

Return per-claim yes/no/unclear diabinfo attribution with source locations and rule
versions. Never ask a model to verify the cited page's support.

**Checks:**
1. A clear association goes to Category 1 without retrieval/support calls. A citation
   elsewhere in the answer does not exempt other claims.
2. Incomplete capture/ambiguous paragraph scope returns `unclear`, excluded from
   definitely-uncited counts. Assessable other-source-only claims go to matching.
3. Hostname tests accept diabinfo.de and subdomains listed in the D07 mapping
   configuration, and reject lookalikes. A real observation/claim pair produces
   traceable mappings or explicit uncertainty.

**Stop:** website support checks, extraction changes or general citation-quality analysis.

### T06 — Usable five-page corpus

**Build:** T00 + HTML fixtures. **Integrate:** T11A + five pilot pages. **Decisions:** D06.  
**Tools / files:** code + LlamaIndex ingestion; `corpus/`, manifests/configuration/tests.

Save full raw/cleaned articles, headings, sections and passages. Use natural structure;
record rules removing navigation/consent banners while retaining article references.

**Checks:**
1. All five pages have usable snapshots/passages with URL, hash, fetch time and parser
   version. Missing pages block readiness unless a task/user instruction explicitly
   authorizes a page-list change and the MVP is updated.
2. Every passage slices to its version. Re-ingestion keeps old versions; changed
   content/parsing creates new ones. Inspect text, headings and lists on every page.
3. Failed/unusable pages have explicit statuses and stay outside the ready corpus.
   Error handling does not satisfy successful ingestion.

**Stop:** PDFs, video, whole-site crawling, rewriting, embeddings or selecting pages
to manufacture positive findings.

**T06 status — 19 September 2026: live_acceptance_passed / merged.**
The original six-GET batch and separate one-SVG authorization are fully consumed.
Both captures remain restricted in the durable private T11A store. The user approved
D06's textual-corpus rule: all deterministically extractable text must be represented;
captured non-text informational visuals remain explicit audited limitations.
Offline `diabinfo-pilot/4` / parser 5 validates the exact parent/asset/authorization/
receipt/no-text-inspection chain before writes, then derives five usable articles
with 228 passages from parser-4 predecessors. Ramadan adds 27 textual passages and
a required restricted `captured_nontext_informational` media-evidence companion.
Its visual is not decorative; no text is inferred. The other four pages retain
identical cleaned wording and passage contents. Completion/load require all media
dependencies; missing/corrupt evidence fails closed. Unknown media remains blocked.
Historical parsers 1–4, rejected diagnostics, and capture artifacts remain immutable.
Source coverage, spans, full Ramadan text inspection and socket-blocked reopen/replay
passed. No refetch, OCR, image interpretation, model calls, shared-schema change,
T07 work. See [T06 handoff](t06-handoff.md) for IDs and validation results.
PR #7 merged as `579ad7571841394256de5e80d94775ccb3da1492`.

### T07 — Hybrid retrieval and context

**Build:** T00 + claim/passage fixtures + retrieval libraries.  
**Integrate:** T06, T11A, embeddings; T04 connects in T11B. **Decisions:** D05/D06.  
**Tools / files:** LlamaIndex, embeddings, BM25, code rank fusion; `retrieval/`, config/tests.

Retrieve semantic candidates with normalized claims and BM25 candidates with original
spans. Use shared passage IDs; merge/deduplicate/fuse ranks, attach saved context and
record settings, path ranks/scores and truncation.

**Checks:**
1. Each path receives its intended input; duplicate passages retain both ranks/scores
   in one candidate. Fixture lists produce the expected fused order.
2. Reject corpus/index or embedding-dimension mismatches. Check German lexical
   settings and numerical tokens explicitly.
3. Build/reload both indexes on the versioned pilot corpus; retrieve for a traceable claim.
   Candidate/context IDs resolve. Report results without claiming recall.

**Stop:** Jev, query expansion, embedding comparisons or calibration.

### T08 — Candidate verification and correspondence

**Build:** T00, T03 interface, candidate fixtures. **Integrate:** T03, T07, T11A.  
**Decisions:** D07. **Tools / files:** Jev; `evidence/candidate_verifier.py`,
`evidence/correspondence.py`, their rubrics/tests only.

Apply Architecture Section 6.1's distinct questions: worth examining, then actual
correspondence. Preserve both decisions.

**Checks:**
1. Controlled decisions exclude/record clear irrelevance, retain uncertainty and send
   relevant-but-nonmatching material to correspondence judging.
2. Partial stays partial; failures/invalid output never become `no_match`. Unfinished
   or budget-truncated candidate sets cannot yield complete negative findings.
   Preserve scores, decisions and versions.
3. Run a bounded real candidate set through both live stages; inspect the trace.
   Record settings without claiming two stages outperform one.

**Stop:** citation fidelity, alternative collection, final categories or calibration.

### T09 — Captured alternative-source excerpts

**Build:** T00, T03 interface, excerpt fixtures. **Integrate:** T01, T03, T08, T11A.  
**Decisions:** D07. **Tools / files:** code selects, Jev compares; `evidence/alternatives.py`,
its rubric/tests.

Use only observation excerpts. Preserve source links, inspected/unassessed states,
correspondence decisions, coverage gaps and known duplicate relationships.

**Checks:**
1. URLs/fan-out queries without text stay unassessed. Network tests show no page
   fetching or independent search.
2. Positive results resolve to the compared excerpt; negatives make no claim about
   unseen content. Exact duplicates are not independent confirmations.
3. Process captured live source material. No usable excerpts yields insufficient
   coverage with a reason—not rarity. This limitation is a valid result.

**Stop:** extra fetching/search or category changes. Even listed-page fetching needs
a separate task explicitly authorizing that scope change.

### T10 — Evidence classification

**Build:** T00 + evidence fixtures. **Integrate:** T03, T05, T08, T09, T11A + rubric
recorded under D07. **Decisions:** D07.  
**Tools / files:** Jev + code guards; `evidence/classifier.py`, its rubric/tests.

Apply Architecture Section 6.2 to full evidence, not scores alone. Create/version the
rubric in this task; resolve D07 before live use. Keep one finding per claim/run
linked to all supporting pair-level records.

**Checks:**
1. Synthetic fixtures exercise all categories/unresolved states under the rubric.
   Category 1 requires citation presence only, with no support call. This tests
   behaviour, not real-data accuracy.
2. Missing alternatives block Category 4 even with a high model score. Unclear
   citations, partial matches, failures and no matches retain their correct statuses.
3. Classify a real saved bundle; call Jev only when guards allow. Save provisional
   scores, evidence and versions. No category may be the correct result.

**Stop:** new categories, calibration, proven provenance or invented model reasoning.
A real Category 4 case is not required.

### T11B — Pipeline execution and restart handling

**Build:** T00, T11A, component doubles. **Integrate:** T01–T10 + D08 pilot manifest.  
**Decisions:** D08/D09. **Tools / files:** code; `runs/`, run configuration/tests.

Connect processing via T11A storage. Save manifests, step attempts, progress/outcomes.
Distinguish capture, reanalysis and resume. Set concurrency, retries, timeouts and
paid-call limits before execution.

**Checks:**
1. Restart reuses completed outputs; changed analysis settings create a new run
   without overwriting findings/reviews.
2. An uncertain paid timeout causes no repeat outside authorized retry limits.
   Budget exhaustion stops calls and records incomplete work, not successful empty results.
3. Execute the D08 pilot manifest. Every attempted observation has a final or explicit
   blocked/failed state; at least one real observation completes analysis. Errors
   prevent labeling the whole run successful.

**Stop:** large-scale scheduling, extra services, API/UI or automatic tuning.

### T12 — API, permissions and metrics

**Build:** T00, T11A, contract/run fixtures. **Integrate:** T11B + access mechanism.  
**Decisions:** D09/D10. **Tools / files:** backend framework; `api/`, tests, generated API reference.

Expose authorized run creation/progress, stored evidence, metrics and append-only
reviews. Return run identity and denominator exclusions. Interactive reads trigger
no provider/model work.

**Checks:**
1. Reject invalid requests and unauthorized reads/reviews/runs. Readers cannot review
   or spend. Authorized reviews retain identity and survive reload.
2. Count answers for answer-level metrics and claims for claim-level metrics;
   multiple passages never multiply claims. Do not pool reanalyses or diagnostics
   into monitoring. Show unknown/missing-data exclusions, not negatives.
3. An authorized operator starts a bounded integrated run and reads saved progress
   without blocking on a long model call. Raw artifacts stay restricted; no secrets
   are returned.

**Stop:** frontend, CMS, new analytics, automatic advice or tenant management.

### T13 — Editorial dashboard

**Build:** T12 contract + labeled mock server. **Integrate:** T12 + findings/accounts.  
**Decisions:** D09/D10. **Tools / files:** frontend framework; `frontend/`, UI/integration tests.

Show runs/queries, original answers/claims, source/alternative evidence, filters,
provisional categories, unresolved states and review controls. Use only the API.

**Checks:**
1. An editor inspects a finding, reviews it and reloads the saved decision. Automated
   output and review stay visibly separate.
2. German/emoji highlights match backend slices. Unknown, failed and insufficient
   states remain visible. Scores are not labeled provenance probabilities.
3. Reader controls and API permissions prevent review/run actions. Captured markup
   cannot execute scripts; bundles contain no provider credentials.

**Stop:** CMS, rewriting, clinical advice, alerts or extra model calls.

### T14 — End-to-end checks and deployment

**Build:** component/API contracts + container/test setup.  
**Integrate:** T01–T10, T11A, T11B, T12, T13. **Decisions:** D08–D10 resolved.  
**Tools / files:** integration tests, CI, containers/deployment, README; coordinate shared config.

Pass and report these gates separately:

| Gate | Required demonstration |
|---|---|
| Offline replay | Labeled saved-data/double run passes contracts, routing and persistence without paid calls. |
| Live integration | A real Google AI Mode capture obtained within authorized limits passes applicable selected model/retrieval stages against the ready five-page corpus. Save finding/justified unresolved outcome, real outputs and errors; no silent substitute. |
| Deployed review | An authenticated editor opens that real result in the deployed API/dashboard, inspects evidence, saves a review and retrieves it after restart. |

**Checks:**
1. All three gates have results. Offline success cannot replace live/deployed checks;
   failed-page records cannot replace a ready corpus. Category 4 is not required.
2. Execute the D08 question manifest within its recorded limits with per-item outcomes.
   Setup and restart/restore checks preserve versions, run identity and reviews.
   Report partial failures.
3. Health/run-failure visibility, secrets and access checks pass. Handoff states
   what ran, mocks, spend uncertainty and limitations. Any blocked required gate
   prevents claiming MVP completion.

**Stop:** systematic evaluation, performance promises, calibration or product expansion.

## 5. Branch handoff and completion report

Use the [concise handoff guidance and template](development-workflow.md#handoffs)
and follow [AGENTS.md](../AGENTS.md) for acceptance and reporting requirements.
Task cards above retain ownership of required checks and stop boundaries.
